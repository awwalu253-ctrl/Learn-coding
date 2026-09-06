# backend/routes/leaderboard.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from ..extensions import db
from ..models.user import User, CourseEnrollment
from ..models.quiz import QuizAnswer
from ..models.course import Course
from ..utils.decorators import admin_required

leaderboard_bp = Blueprint('leaderboard', __name__)

@leaderboard_bp.route('/')
@login_required
def index():
    if current_user.is_admin():
        return redirect(url_for('leaderboard.admin'))
    
    enrolled_courses = current_user.get_enrolled_courses()
    enrolled_course_ids = [c.id for c in enrolled_courses]
    
    students = User.query.filter_by(role='student', is_approved=True).all()
    student_scores = []
    
    for student in students:
        answers = QuizAnswer.query.filter_by(student_id=student.id).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        score = int((correct / total) * 100) if total > 0 else 0
        
        student_scores.append({
            'student': student,
            'score': score,
            'total_questions': total
        })
    
    student_scores.sort(key=lambda x: x['score'], reverse=True)
    
    return render_template('leaderboard.html', student_scores=student_scores)


@leaderboard_bp.route('/admin')
@login_required
@admin_required
def admin():
    """Admin leaderboard page with course filtering"""
    # Get all courses for the filter dropdown
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    # Get selected course filter
    course_id = request.args.get('course_id', type=int)
    selected_course = None
    selected_course_id = None
    
    if course_id and course_id > 0:
        selected_course = Course.query.get(course_id)
        if selected_course:
            selected_course_id = course_id
    
    # Get students based on filter
    if selected_course:
        # Get students enrolled in the selected course
        student_ids = db.session.query(CourseEnrollment.student_id).filter(
            CourseEnrollment.course_id == selected_course.id,
            CourseEnrollment.status == 'approved'
        ).distinct().all()
        student_ids = [s[0] for s in student_ids]
        students = User.query.filter(
            User.role == 'student',
            User.is_approved == True,
            User.id.in_(student_ids)
        ).all() if student_ids else []
    else:
        students = User.query.filter_by(role='student', is_approved=True).all()
    
    student_scores = []
    for student in students:
        answers = QuizAnswer.query.filter_by(student_id=student.id).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        score = int((correct / total) * 100) if total > 0 else 0
        
        student_courses = student.get_enrolled_courses()
        
        # Get course progress if filtering by course
        course_progress = None
        if selected_course:
            course_progress = selected_course.get_progress_for_student(student.id)
        
        student_scores.append({
            'student': student,
            'score': score,
            'correct': correct,
            'total': total,
            'course_count': len(student_courses),
            'courses': [c.name for c in student_courses[:3]],
            'joined': student.created_at.strftime('%b %d, %Y') if student.created_at else 'N/A',
            'status': 'Active' if student.is_approved else 'Pending',
            'course_names': ', '.join([c.name for c in student_courses[:3]]) + ('...' if len(student_courses) > 3 else ''),
            'course_progress': course_progress
        })
    
    # Sort by score descending (highest first)
    student_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Calculate stats
    total_students = len(student_scores)
    avg_score = round(sum(s['score'] for s in student_scores) / total_students, 1) if total_students > 0 else 0
    
    # Get top performer (first item after sorting)
    top_performer = student_scores[0] if student_scores else None
    
    return render_template('admin/leaderboard.html',
                         student_scores=student_scores,
                         total_students=total_students,
                         avg_score=avg_score,
                         top_performer=top_performer,
                         courses=courses,
                         selected_course=selected_course,
                         selected_course_id=selected_course_id)


@leaderboard_bp.route('/course/<int:course_id>')
@login_required
def course_leaderboard(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not current_user.is_admin() and not current_user.is_enrolled_in_course(course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('leaderboard.index'))
    
    enrollments = CourseEnrollment.query.filter_by(
        course_id=course_id,
        status='approved'
    ).all()
    
    student_ids = [e.student_id for e in enrollments]
    students = User.query.filter(User.id.in_(student_ids)).all()
    
    student_scores = []
    for student in students:
        answers = QuizAnswer.query.filter_by(student_id=student.id).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        score = int((correct / total) * 100) if total > 0 else 0
        
        student_scores.append({
            'student': student,
            'score': score,
            'total_questions': total
        })
    
    student_scores.sort(key=lambda x: x['score'], reverse=True)
    
    return render_template('leaderboard_course.html', 
                         student_scores=student_scores, 
                         course=course)


@leaderboard_bp.route('/export')
@login_required
@admin_required
def export():
    """Export leaderboard data as CSV with course filtering"""
    import csv
    from io import StringIO
    
    course_id = request.args.get('course_id', type=int)
    selected_course = None
    
    if course_id and course_id > 0:
        selected_course = Course.query.get(course_id)
    
    if selected_course:
        student_ids = db.session.query(CourseEnrollment.student_id).filter(
            CourseEnrollment.course_id == selected_course.id,
            CourseEnrollment.status == 'approved'
        ).distinct().all()
        student_ids = [s[0] for s in student_ids]
        students = User.query.filter(
            User.role == 'student',
            User.is_approved == True,
            User.id.in_(student_ids)
        ).all() if student_ids else []
    else:
        students = User.query.filter_by(role='student', is_approved=True).all()
    
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Rank', 'Student', 'Email', 'Score', 'Correct', 'Total', 'Courses', 'Joined'])
    
    for rank, student in enumerate(students, 1):
        answers = QuizAnswer.query.filter_by(student_id=student.id).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        score = int((correct / total) * 100) if total > 0 else 0
        
        writer.writerow([
            rank,
            student.username,
            student.email,
            f"{score}%",
            correct,
            total,
            len(student.get_enrolled_courses()),
            student.created_at.strftime('%Y-%m-%d') if student.created_at else 'N/A'
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=leaderboard_export{"_" + selected_course.code if selected_course else ""}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response


@leaderboard_bp.route('/reset/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def reset_student(student_id):
    """Reset a student's quiz scores"""
    student = User.query.get_or_404(student_id)
    
    if not current_user.is_super_admin():
        flash('Only super admin can reset scores.', 'error')
        return redirect(url_for('leaderboard.admin'))
    
    QuizAnswer.query.filter_by(student_id=student_id).delete()
    db.session.commit()
    
    flash(f'All quiz scores for {student.username} have been reset.', 'success')
    return redirect(url_for('leaderboard.admin'))


@leaderboard_bp.route('/reset-all', methods=['POST'])
@login_required
@admin_required
def reset_all():
    """Reset all student quiz scores"""
    if not current_user.is_super_admin():
        flash('Only super admin can reset all scores.', 'error')
        return redirect(url_for('leaderboard.admin'))
    
    QuizAnswer.query.delete()
    db.session.commit()
    
    flash('All student quiz scores have been reset.', 'success')
    return redirect(url_for('leaderboard.admin'))