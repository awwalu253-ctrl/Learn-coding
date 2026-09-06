# backend/routes/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import or_
from ..extensions import db
from ..models.user import User, CourseEnrollment
from ..models.course import Course
from ..models.note import Note, Tag
from ..models.quiz import QuizGroup, QuizAnswer, QuizQuestion
from ..models.assignment import Assignment, AssignmentSubmission
from ..models.notification import Notification, RejectionMessage
from ..models.announcement import Announcement
from ..models.system import SystemSetting
from ..utils.decorators import admin_required, super_admin_required
from ..services.notification_service import create_notification, notify_course_approved, notify_student_approved, notify_student_rejected, notify_student_suspended, notify_student_unsuspended

admin_bp = Blueprint('admin', __name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_admin_upcoming_deadlines(admin_user):
    """Get upcoming deadlines for admin dashboard"""
    if admin_user.is_super_admin():
        course_ids = [c.id for c in Course.query.all()]
    else:
        course_ids = [c.id for c in admin_user.managed_courses]
    
    now = datetime.utcnow()
    upcoming = Assignment.query.filter(
        Assignment.course_id.in_(course_ids),
        Assignment.due_date >= (now - timedelta(days=7))
    ).order_by(Assignment.due_date.asc()).limit(10).all()
    
    deadlines = []
    for assignment in upcoming:
        days_until = (assignment.due_date - now).days
        if days_until < 0:
            status = 'overdue'
            status_text = f'Overdue by {abs(days_until)}d'
        elif days_until == 0:
            status = 'today'
            status_text = 'Today'
        elif days_until <= 3:
            status = 'soon'
            status_text = f'{days_until}d left'
        else:
            status = 'upcoming'
            status_text = f'{days_until}d left'
        
        submissions_count = AssignmentSubmission.query.filter_by(
            assignment_id=assignment.id
        ).count()
        
        total_students = CourseEnrollment.query.filter_by(
            course_id=assignment.course_id,
            status='approved'
        ).count()
        
        deadlines.append({
            'id': assignment.id,
            'title': assignment.title,
            'course_name': assignment.course.name,
            'due_date': assignment.due_date,
            'days_until': days_until,
            'status': status,
            'status_text': status_text,
            'submissions_count': submissions_count,
            'total_students': total_students
        })
    
    return deadlines


def get_admin_quiz_results(admin_user):
    """Get quiz results for admin dashboard"""
    if admin_user.is_super_admin():
        course_ids = [c.id for c in Course.query.all()]
    else:
        course_ids = [c.id for c in admin_user.managed_courses]
    
    quiz_groups = QuizGroup.query.filter(QuizGroup.course_id.in_(course_ids)).all()
    
    results = []
    for quiz in quiz_groups:
        answers = QuizAnswer.query.filter_by(quiz_group_id=quiz.id).all()
        
        if answers:
            student_scores = {}
            for answer in answers:
                if answer.student_id not in student_scores:
                    student_scores[answer.student_id] = {'correct': 0, 'total': 0}
                student_scores[answer.student_id]['total'] += 1
                if answer.is_correct:
                    student_scores[answer.student_id]['correct'] += 1
            
            if student_scores:
                total_score = 0
                for s in student_scores.values():
                    total_score += (s['correct'] / s['total']) * 100 if s['total'] > 0 else 0
                avg_score = total_score / len(student_scores)
            else:
                avg_score = 0
            
            latest = QuizAnswer.query.filter_by(
                quiz_group_id=quiz.id
            ).order_by(QuizAnswer.answered_at.desc()).first()
            
            results.append({
                'quiz_id': quiz.id,
                'title': quiz.title,
                'course_name': quiz.course.name,
                'avg_score': round(avg_score, 1),
                'total_students': len(student_scores),
                'latest_submission': latest.answered_at if latest else None,
                'color_class': 'high' if avg_score >= 70 else 'medium' if avg_score >= 50 else 'low'
            })
        else:
            results.append({
                'quiz_id': quiz.id,
                'title': quiz.title,
                'course_name': quiz.course.name,
                'avg_score': 0,
                'total_students': 0,
                'latest_submission': None,
                'color_class': 'low'
            })
    
    results.sort(key=lambda x: x['latest_submission'] or datetime(1970, 1, 1), reverse=True)
    return results[:10]


def get_admin_announcements_with_pins(admin_user):
    """Get announcements with pins for admin dashboard"""
    if admin_user.is_super_admin():
        announcements = Announcement.query.order_by(
            Announcement.is_pinned.desc(),
            Announcement.created_at.desc()
        ).limit(6).all()
    else:
        course_ids = [c.id for c in admin_user.managed_courses]
        announcements = Announcement.query.filter(
            or_(
                Announcement.course_id.in_(course_ids),
                Announcement.course_id.is_(None)
            )
        ).order_by(
            Announcement.is_pinned.desc(),
            Announcement.created_at.desc()
        ).limit(6).all()
    
    result = []
    for ann in announcements:
        result.append({
            'id': ann.id,
            'title': ann.title,
            'content': ann.content,
            'is_pinned': ann.is_pinned,
            'course_name': ann.course.name if ann.course else 'Global',
            'created_at': ann.created_at,
            'author': ann.author.username if ann.author else 'System'
        })
    
    return result


def get_admin_notices_with_ctas(admin_user):
    """Get notices with CTAs for admin dashboard"""
    notices = []
    
    pending_students = User.query.filter_by(role='student', is_approved=False).count()
    if pending_students > 0:
        notices.append({
            'type': 'warning',
            'icon': 'fa-user-clock',
            'icon_color': 'orange',
            'title': f'{pending_students} Student(s) Pending Approval',
            'message': f'{pending_students} students are waiting for account approval.',
            'cta_text': 'Review Students',
            'cta_url': url_for('admin.manage_students'),
            'priority': 'high',
            'dismissible': False
        })
    
    pending_enrollments = CourseEnrollment.query.filter_by(status='pending').count()
    if pending_enrollments > 0:
        notices.append({
            'type': 'info',
            'icon': 'fa-book-open',
            'icon_color': 'gold',
            'title': f'{pending_enrollments} Pending Course Request(s)',
            'message': 'Students are waiting for course approval.',
            'cta_text': 'Review Requests',
            'cta_url': url_for('admin.manage_students'),
            'priority': 'medium',
            'dismissible': True
        })
    
    return notices


def get_admin_enhanced_activity(admin_user, limit=15):
    """Get enhanced recent activity feed with icons and colors"""
    activities = []
    
    if admin_user.is_super_admin():
        course_ids = [c.id for c in Course.query.all()]
    else:
        course_ids = [c.id for c in admin_user.managed_courses]
    
    # Get recent notes
    notes = Note.query.filter(
        Note.course_id.in_(course_ids),
        Note.created_at >= (datetime.utcnow() - timedelta(days=30))
    ).order_by(Note.created_at.desc()).limit(10).all()
    
    for note in notes:
        activities.append({
            'type': 'note',
            'icon': 'fa-file-alt',
            'color': 'blue',
            'title': f'📝 New Note: "{note.title}"',
            'description': f'Posted in {note.course.name}',
            'time': note.created_at,
            'user': note.author.username if note.author else 'System',
            'url': url_for('note.edit_note', note_id=note.id) if note.id else None,
            'badge': 'New' if note.is_new() else None,
            'badge_color': 'green'
        })
    
    # Get recent quiz results
    quiz_answers = QuizAnswer.query.filter(
        QuizAnswer.answered_at >= (datetime.utcnow() - timedelta(days=30))
    ).order_by(QuizAnswer.answered_at.desc()).limit(10).all()
    
    for answer in quiz_answers:
        if answer.quiz_group and answer.quiz_group.course_id in course_ids:
            student = User.query.get(answer.student_id)
            activities.append({
                'type': 'quiz',
                'icon': 'fa-puzzle-piece',
                'color': 'gold',
                'title': f'🎯 Quiz Completed: "{answer.quiz_group.title}"',
                'description': f'{student.username if student else "Student"} scored',
                'time': answer.answered_at,
                'user': student.username if student else 'Unknown',
                'url': url_for('quiz.edit_quiz_group', quiz_id=answer.quiz_group.id) if answer.quiz_group.id else None,
                'badge': 'New' if (datetime.utcnow() - answer.answered_at).days <= 1 else None,
                'badge_color': 'gold'
            })
    
    # Get recent submissions
    submissions = AssignmentSubmission.query.filter(
        AssignmentSubmission.submitted_at >= (datetime.utcnow() - timedelta(days=30))
    ).order_by(AssignmentSubmission.submitted_at.desc()).limit(10).all()
    
    for sub in submissions:
        if sub.assignment and sub.assignment.course_id in course_ids:
            student = User.query.get(sub.student_id)
            activities.append({
                'type': 'submission',
                'icon': 'fa-tasks',
                'color': 'green',
                'title': f'📋 Assignment Submitted: "{sub.assignment.title}"',
                'description': f'{student.username if student else "Student"} submitted work',
                'time': sub.submitted_at,
                'user': student.username if student else 'Unknown',
                'url': url_for('assignment.view_submissions', assignment_id=sub.assignment.id) if sub.assignment.id else None,
                'badge': 'Needs Grading' if not sub.is_graded else None,
                'badge_color': 'orange'
            })
    
    # Get new students
    new_students = User.query.filter(
        User.role == 'student',
        User.created_at >= (datetime.utcnow() - timedelta(days=30))
    ).order_by(User.created_at.desc()).limit(5).all()
    
    for student in new_students:
        activities.append({
            'type': 'student',
            'icon': 'fa-user-plus',
            'color': 'purple',
            'title': f'👤 New Student Registered',
            'description': f'{student.username} ({student.email})',
            'time': student.created_at,
            'user': student.username,
            'url': url_for('admin.edit_student', student_id=student.id) if student.id else None,
            'badge': 'Pending' if not student.is_approved else 'Approved',
            'badge_color': 'orange' if not student.is_approved else 'green'
        })
    
    activities.sort(key=lambda x: x['time'], reverse=True)
    
    seen = set()
    unique_activities = []
    for act in activities:
        key = (act['title'], act['time'].strftime('%Y-%m-%d %H:%M') if act['time'] else '')
        if key not in seen:
            seen.add(key)
            unique_activities.append(act)
    
    return unique_activities[:limit]


def get_student_progress_visualization(admin_user):
    """Get student progress visualization data"""
    if admin_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = admin_user.managed_courses
    
    visualization_data = []
    for course in courses:
        enrollments = CourseEnrollment.query.filter_by(
            course_id=course.id,
            status='approved'
        ).all()
        
        if enrollments:
            progress_values = []
            students = []
            for enrollment in enrollments:
                student = User.query.get(enrollment.student_id)
                if student:
                    progress = course.get_progress_for_student(student.id)
                    progress_values.append(progress)
                    students.append({
                        'name': student.username,
                        'progress': progress
                    })
            
            if progress_values:
                avg_progress = sum(progress_values) / len(progress_values)
                max_progress = max(progress_values)
                min_progress = min(progress_values)
                completed_count = sum(1 for p in progress_values if p >= 100)
            else:
                avg_progress = max_progress = min_progress = completed_count = 0
            
            visualization_data.append({
                'course_id': course.id,
                'course_name': course.name,
                'course_code': course.code,
                'total_students': len(students),
                'avg_progress': round(avg_progress, 1),
                'max_progress': max_progress,
                'min_progress': min_progress,
                'completed_count': completed_count,
                'students': students,
                'progress_distribution': {
                    '0-25': sum(1 for p in progress_values if 0 <= p < 25),
                    '25-50': sum(1 for p in progress_values if 25 <= p < 50),
                    '50-75': sum(1 for p in progress_values if 50 <= p < 75),
                    '75-100': sum(1 for p in progress_values if 75 <= p < 100),
                    '100': sum(1 for p in progress_values if p >= 100)
                }
            })
        else:
            visualization_data.append({
                'course_id': course.id,
                'course_name': course.name,
                'course_code': course.code,
                'total_students': 0,
                'avg_progress': 0,
                'max_progress': 0,
                'min_progress': 0,
                'completed_count': 0,
                'students': [],
                'progress_distribution': {
                    '0-25': 0,
                    '25-50': 0,
                    '50-75': 0,
                    '75-100': 0,
                    '100': 0
                }
            })
    
    return visualization_data


# ============================================================================
# DASHBOARD
# ============================================================================

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_students = User.query.filter_by(role='student').count()
    total_courses = Course.query.count()
    total_notes = Note.query.count()
    total_quizzes = QuizGroup.query.count()
    total_assignments = Assignment.query.count()
    
    pending_approvals = User.query.filter_by(role='student', is_approved=False).count()
    pending = User.query.filter_by(role='student', is_approved=False).all()
    
    pending_enrollments = CourseEnrollment.query.filter_by(status='pending').all()
    pending_course_requests = {}
    for enrollment in pending_enrollments:
        if enrollment.student_id not in pending_course_requests:
            pending_course_requests[enrollment.student_id] = {
                'student': enrollment.student,
                'courses': []
            }
        pending_course_requests[enrollment.student_id]['courses'].append(enrollment.course)
    
    pending_course_requests_list = list(pending_course_requests.values())
    
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    recent_notes = Note.query.order_by(Note.created_at.desc()).limit(5).all()
    recent_quizzes = QuizGroup.query.order_by(QuizGroup.created_at.desc()).limit(5).all()
    
    admin_count = User.query.filter_by(role='admin').count() if current_user.is_super_admin() else 0
    announcements_count = Announcement.query.count()
    tag_count = Tag.query.count()
    student_count = total_students
    
    upcoming_deadlines = get_admin_upcoming_deadlines(current_user)
    quiz_results = get_admin_quiz_results(current_user)
    announcements_with_pins = get_admin_announcements_with_pins(current_user)
    notices = get_admin_notices_with_ctas(current_user)
    enhanced_activity = get_admin_enhanced_activity(current_user)
    progress_visualization = get_student_progress_visualization(current_user)
    
    return render_template('admin/dashboard.html',
                         total_students=total_students,
                         total_courses=total_courses,
                         total_notes=total_notes,
                         total_quizzes=total_quizzes,
                         total_assignments=total_assignments,
                         pending_approvals=pending_approvals,
                         pending=pending,
                         pending_students=pending,
                         pending_course_requests=pending_course_requests_list,
                         pending_course_requests_count=len(pending_course_requests_list),
                         recent_notes=recent_notes,
                         recent_quizzes=recent_quizzes,
                         admin_count=admin_count,
                         announcements_count=announcements_count,
                         tag_count=tag_count,
                         student_count=student_count,
                         courses=courses,
                         upcoming_deadlines=upcoming_deadlines,
                         quiz_results=quiz_results,
                         announcements_with_pins=announcements_with_pins,
                         notices=notices,
                         enhanced_activity=enhanced_activity,
                         progress_visualization=progress_visualization)


# ============================================================================
# STUDENT MANAGEMENT
# ============================================================================

@admin_bp.route('/students')
@login_required
@admin_required
def manage_students():
    # Get filter parameters
    course_id = request.args.get('course_id', type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', 'all')
    
    # Base queries
    if current_user.is_super_admin():
        students_query = User.query.filter_by(role='student')
        pending_query = User.query.filter_by(role='student', is_approved=False)
        all_courses = Course.query.all()
    else:
        course_ids = [c.id for c in current_user.managed_courses]
        students_query = User.query.filter(
            User.role == 'student',
            User.id.in_(
                db.session.query(CourseEnrollment.student_id).filter(
                    CourseEnrollment.course_id.in_(course_ids)
                )
            )
        )
        pending_query = User.query.filter(
            User.role == 'student',
            User.is_approved == False,
            User.id.in_(
                db.session.query(CourseEnrollment.student_id).filter(
                    CourseEnrollment.course_id.in_(course_ids)
                )
            )
        )
        all_courses = current_user.managed_courses
    
    # Apply course filter
    if course_id and course_id > 0:
        course = Course.query.get(course_id)
        if course:
            student_ids = db.session.query(CourseEnrollment.student_id).filter(
                CourseEnrollment.course_id == course.id,
                CourseEnrollment.status == 'approved'
            ).distinct().all()
            student_ids = [s[0] for s in student_ids]
            if student_ids:
                students_query = students_query.filter(User.id.in_(student_ids))
                pending_query = pending_query.filter(User.id.in_(student_ids))
            else:
                students_query = students_query.filter(User.id.in_([-1]))
                pending_query = pending_query.filter(User.id.in_([-1]))
    
    # Apply search filter
    if search:
        search_term = f"%{search}%"
        students_query = students_query.filter(
            db.or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
        pending_query = pending_query.filter(
            db.or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    # Apply status filter
    if status_filter == 'approved':
        students_query = students_query.filter(User.is_approved == True, User.is_suspended == False)
    elif status_filter == 'pending':
        students_query = students_query.filter(User.is_approved == False, User.is_suspended == False)
    elif status_filter == 'suspended':
        students_query = students_query.filter(User.is_suspended == True)
    
    # Execute queries
    students = students_query.order_by(User.created_at.desc()).all()
    pending = pending_query.all()
    
    # Get pending course requests
    if current_user.is_super_admin():
        pending_course_requests = CourseEnrollment.query.filter_by(status='pending').all()
    else:
        course_ids = [c.id for c in current_user.managed_courses]
        pending_course_requests = CourseEnrollment.query.filter(
            CourseEnrollment.status == 'pending',
            CourseEnrollment.course_id.in_(course_ids)
        ).all()
    
    # Group pending course requests by student
    pending_requests_by_student = {}
    for enrollment in pending_course_requests:
        if enrollment.student_id not in pending_requests_by_student:
            pending_requests_by_student[enrollment.student_id] = {
                'student': enrollment.student,
                'enrollments': []
            }
        pending_requests_by_student[enrollment.student_id]['enrollments'].append(enrollment)
    
    pending_requests_list = list(pending_requests_by_student.values())
    
    # Get all courses for filter dropdown
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    return render_template('admin/manage_students.html', 
                         students=students,
                         pending=pending,
                         pending_course_requests=pending_requests_list,
                         pending_course_requests_count=len(pending_course_requests),
                         courses=courses,
                         selected_course_id=course_id,
                         search_query=search,
                         status_filter=status_filter)


@admin_bp.route('/students/bulk-approve-courses', methods=['POST'])
@login_required
@admin_required
def bulk_approve_courses():
    """Bulk approve all pending course requests"""
    try:
        # Get all pending enrollments
        pending_enrollments = CourseEnrollment.query.filter_by(status='pending').all()
        
        if not pending_enrollments:
            flash('No pending course requests found.', 'info')
            return redirect(url_for('admin.manage_students'))
        
        approved_count = 0
        students_approved = set()
        
        for enrollment in pending_enrollments:
            try:
                enrollment.status = 'approved'
                enrollment.approved_at = datetime.utcnow()
                approved_count += 1
                students_approved.add(enrollment.student_id)
            except Exception as e:
                print(f"Error approving enrollment {enrollment.id}: {e}")
                continue
        
        # Approve the students who had courses approved
        for student_id in students_approved:
            try:
                student = User.query.get(student_id)
                if student and not student.is_approved:
                    student.is_approved = True
            except Exception as e:
                print(f"Error approving student {student_id}: {e}")
        
        db.session.commit()
        
        # Send notifications to students
        for enrollment in pending_enrollments:
            try:
                student = User.query.get(enrollment.student_id)
                if student:
                    # Get course object for the link
                    course = Course.query.get(enrollment.course_id)
                    if course:
                        notify_course_approved(student.id, course.name)
                    else:
                        # Fallback without course object
                        create_notification(
                            user_id=student.id,
                            title='✅ Course Approved!',
                            message=f'You have been approved for a course.',
                            type='success',
                            link=url_for('student.courses'),
                            icon='fa-check-circle',
                            icon_color='green'
                        )
            except Exception as e:
                print(f"Error sending notification for enrollment {enrollment.id}: {e}")
        
        flash(f'{approved_count} course requests approved successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in bulk_approve_courses: {e}")
        flash(f'Error approving courses: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_student(student_id):
    student = User.query.get_or_404(student_id)
    courses = Course.query.all()
    
    enrollments = CourseEnrollment.query.filter_by(student_id=student.id).all()
    enrolled_course_ids = [e.course_id for e in enrollments]
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        is_approved = request.form.get('is_approved') == 'on'
        selected_courses = request.form.getlist('courses')
        
        student.username = username
        student.email = email
        student.is_approved = is_approved
        
        current_enrollments = CourseEnrollment.query.filter_by(student_id=student.id).all()
        current_course_ids = [e.course_id for e in current_enrollments]
        
        for course_id in selected_courses:
            course_id_int = int(course_id)
            if course_id_int not in current_course_ids:
                enrollment = CourseEnrollment(
                    student_id=student.id,
                    course_id=course_id_int,
                    status='pending'
                )
                db.session.add(enrollment)
        
        for enrollment in current_enrollments:
            if enrollment.course_id not in [int(c) for c in selected_courses]:
                db.session.delete(enrollment)
        
        db.session.commit()
        flash(f'Student {student.username} updated successfully!', 'success')
        return redirect(url_for('admin.manage_students'))
    
    return render_template('admin/edit_student.html', 
                         student=student, 
                         courses=courses,
                         enrolled_course_ids=enrolled_course_ids)


@admin_bp.route('/students/<int:student_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_student(student_id):
    student = User.query.get_or_404(student_id)
    student.is_approved = True
    db.session.commit()
    
    notify_student_approved(student.id)
    
    flash(f'{student.username} has been approved.', 'success')
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_student(student_id):
    student = User.query.get_or_404(student_id)
    
    if student.is_admin():
        flash('Cannot delete admin accounts.', 'error')
        return redirect(url_for('admin.manage_students'))
    
    CourseEnrollment.query.filter_by(student_id=student.id).delete()
    Notification.query.filter_by(user_id=student.id).delete()
    QuizAnswer.query.filter_by(student_id=student.id).delete()
    AssignmentSubmission.query.filter_by(student_id=student.id).delete()
    
    db.session.delete(student)
    db.session.commit()
    
    flash(f'Student {student.username} deleted.', 'success')
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/students/bulk-approve', methods=['POST'])
@login_required
@admin_required
def bulk_approve_students():
    if not current_user.is_super_admin():
        flash('Only Super Admin can bulk approve students.', 'error')
        return redirect(url_for('admin.manage_students'))
    
    student_ids = request.form.getlist('student_ids')
    
    if not student_ids:
        flash('No students selected.', 'warning')
        return redirect(url_for('admin.manage_students'))
    
    approved_count = 0
    for sid in student_ids:
        student = User.query.get(sid)
        if student and student.role == 'student':
            student.is_approved = True
            pending_enrollments = CourseEnrollment.query.filter_by(
                student_id=student.id,
                status='pending'
            ).all()
            for enrollment in pending_enrollments:
                enrollment.status = 'approved'
                enrollment.approved_at = datetime.utcnow()
            approved_count += 1
            
            notify_student_approved(student.id)
    
    db.session.commit()
    flash(f'{approved_count} students approved successfully.', 'success')
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/students/<int:student_id>/approve-course/<int:course_id>', methods=['POST'])
@login_required
@admin_required
def approve_course(student_id, course_id):
    student = User.query.get_or_404(student_id)
    course = Course.query.get_or_404(course_id)
    
    enrollment = CourseEnrollment.query.filter_by(
        student_id=student.id,
        course_id=course.id,
        status='pending'
    ).first()
    
    if enrollment:
        enrollment.status = 'approved'
        enrollment.approved_at = datetime.utcnow()
        db.session.commit()
        
        notify_course_approved(student.id, course.name)
        
        flash(f'{student.username} approved for {course.name}.', 'success')
    else:
        flash('No pending enrollment found.', 'error')
    
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/students/<int:student_id>/reject', methods=['GET', 'POST'])
@login_required
@admin_required
def reject_student(student_id):
    student = User.query.get_or_404(student_id)
    
    pending_enrollments = CourseEnrollment.query.filter_by(
        student_id=student.id,
        status='pending'
    ).all()
    
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        message = request.form.get('message')
        
        if not course_id or not message:
            flash('Please select a course and provide a reason.', 'error')
            return render_template('admin/reject_user.html', student=student, enrollments=pending_enrollments)
        
        enrollment = CourseEnrollment.query.filter_by(
            student_id=student.id,
            course_id=course_id,
            status='pending'
        ).first()
        
        if enrollment:
            enrollment.status = 'rejected'
            enrollment.rejected_at = datetime.utcnow()
            enrollment.rejection_reason = message
            
            rejection = RejectionMessage(
                student_id=student.id,
                course_id=course_id,
                message=message
            )
            db.session.add(rejection)
            
            notify_student_rejected(student.id, enrollment.course.name, message)
            
            db.session.commit()
            flash(f'{student.username} rejected from {enrollment.course.name}.', 'warning')
        
        return redirect(url_for('admin.manage_students'))
    
    return render_template('admin/reject_user.html', student=student, enrollments=pending_enrollments)


@admin_bp.route('/students/<int:student_id>/suspend', methods=['GET', 'POST'])
@login_required
@admin_required
def suspend_student(student_id):
    student = User.query.get_or_404(student_id)
    
    if student.is_admin():
        flash('Cannot suspend admin accounts.', 'error')
        return redirect(url_for('admin.manage_students'))
    
    if request.method == 'POST':
        reason = request.form.get('reason', 'No reason provided.')
        
        student.is_suspended = True
        student.suspension_reason = reason
        student.suspended_at = datetime.utcnow()
        student.is_approved = False
        
        db.session.commit()
        
        notify_student_suspended(student.id, reason)
        
        flash(f'{student.username} has been suspended.', 'warning')
        return redirect(url_for('admin.manage_students'))
    
    return render_template('admin/suspend_student.html', student=student)


@admin_bp.route('/students/<int:student_id>/unsuspend', methods=['POST'])
@login_required
@admin_required
def unsuspend_student(student_id):
    student = User.query.get_or_404(student_id)
    
    student.is_suspended = False
    student.suspension_reason = None
    student.suspended_at = None
    
    db.session.commit()
    
    notify_student_unsuspended(student.id)
    
    flash(f'{student.username} has been unsuspended.', 'success')
    return redirect(url_for('admin.manage_students'))


# ============================================================================
# COURSE MANAGEMENT
# ============================================================================

@admin_bp.route('/courses')
@login_required
@admin_required
def course_list():
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    course_data = []
    for course in courses:
        enrollments = CourseEnrollment.query.filter_by(course_id=course.id).all()
        course_data.append({
            'course': course,
            'total_students': len(enrollments),
            'approved_students': sum(1 for e in enrollments if e.status == 'approved'),
            'pending_students': sum(1 for e in enrollments if e.status == 'pending'),
            'notes_count': len(course.notes),
            'quizzes_count': len(course.quiz_groups),
            'assignments_count': len(course.assignments)
        })
    
    return render_template('admin/course_list.html', courses=course_data)


@admin_bp.route('/courses/<int:course_id>')
@login_required
@admin_required
def course_detail(course_id):
    """View course details with all enrollments"""
    course = Course.query.get_or_404(course_id)
    
    # Check permission
    if not current_user.is_super_admin() and course not in current_user.managed_courses:
        flash('You do not have permission to view this course.', 'error')
        return redirect(url_for('admin.course_list'))
    
    # Get assigned admins
    admins = course.admins if hasattr(course, 'admins') else []
    if not admins:
        admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    
    # Get all enrollments for this course
    enrollments = CourseEnrollment.query.filter_by(course_id=course.id).all()
    
    # Prepare student data
    students_data = []
    for enrollment in enrollments:
        student = User.query.get(enrollment.student_id)
        if student:
            students_data.append({
                'student': student,
                'status': enrollment.status,
                'requested_at': enrollment.requested_at,
                'approved_at': enrollment.approved_at,
                'rejected_at': enrollment.rejected_at,
                'rejection_reason': enrollment.rejection_reason
            })
    
    # Get notes, quizzes, assignments
    notes = Note.query.filter_by(course_id=course.id).order_by(Note.created_at.desc()).all()
    quizzes = QuizGroup.query.filter_by(course_id=course.id).all()
    assignments = Assignment.query.filter_by(course_id=course.id).all()
    
    # Calculate stats
    total_students = len(students_data)
    approved_count = sum(1 for s in students_data if s['status'] == 'approved')
    pending_count = sum(1 for s in students_data if s['status'] == 'pending')
    rejected_count = sum(1 for s in students_data if s['status'] == 'rejected')
    
    return render_template('admin/course_detail.html',
                         course=course,
                         admins=admins,
                         students=students_data,
                         total_students=total_students,
                         approved_count=approved_count,
                         pending_count=pending_count,
                         rejected_count=rejected_count,
                         notes=notes,
                         quizzes=quizzes,
                         assignments=assignments,
                         is_super_admin=current_user.is_super_admin())


@admin_bp.route('/courses/<int:course_id>/student/<int:student_id>/view')
@login_required
@admin_required
def view_student_in_course(course_id, student_id):
    """View a student's progress in a specific course"""
    course = Course.query.get_or_404(course_id)
    student = User.query.get_or_404(student_id)
    
    if not current_user.is_super_admin() and course not in current_user.managed_courses:
        flash('You do not have permission to view this course.', 'error')
        return redirect(url_for('admin.course_list'))
    
    # Check if student is enrolled
    enrollment = CourseEnrollment.query.filter_by(
        student_id=student.id,
        course_id=course.id
    ).first()
    
    if not enrollment:
        flash('Student is not enrolled in this course.', 'error')
        return redirect(url_for('admin.course_detail', course_id=course_id))
    
    # Get student progress
    progress = course.get_progress_for_student(student.id)
    
    # Get quiz results for this course
    quiz_answers = QuizAnswer.query.filter_by(student_id=student.id).all()
    quiz_results = []
    for answer in quiz_answers:
        if answer.quiz_group and answer.quiz_group.course_id == course.id:
            score = answer.quiz_group.get_student_score(student.id)
            if score:
                quiz_results.append({
                    'title': answer.quiz_group.title,
                    'score': score
                })
    
    # Get assignment submissions for this course
    submissions = AssignmentSubmission.query.filter_by(student_id=student.id).all()
    assignment_results = []
    for sub in submissions:
        if sub.assignment and sub.assignment.course_id == course.id:
            assignment_results.append({
                'title': sub.assignment.title,
                'submitted_at': sub.submitted_at,
                'score': sub.score,
                'is_graded': sub.is_graded,
                'feedback': sub.feedback
            })
    
    return render_template('admin/student_course_detail.html',
                         course=course,
                         student=student,
                         enrollment=enrollment,
                         progress=progress,
                         quiz_results=quiz_results,
                         assignment_results=assignment_results)


@admin_bp.route('/courses/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_course():
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        description = request.form.get('description')
        
        if not name or not code:
            flash('Course name and code are required.', 'error')
            return render_template('admin/create_course.html')
        
        if Course.query.filter_by(code=code).first():
            flash('Course code already exists.', 'error')
            return render_template('admin/create_course.html')
        
        course = Course(name=name, code=code, description=description)
        db.session.add(course)
        db.session.commit()
        
        flash(f'Course {name} created successfully!', 'success')
        return redirect(url_for('admin.course_list'))
    
    return render_template('admin/create_course.html')


@admin_bp.route('/courses/<int:course_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    CourseEnrollment.query.filter_by(course_id=course_id).delete()
    db.session.delete(course)
    db.session.commit()
    
    flash(f'Course {course.name} deleted.', 'success')
    return redirect(url_for('admin.course_list'))


# ============================================================================
# ANNOUNCEMENTS
# ============================================================================

@admin_bp.route('/announcements')
@login_required
@admin_required
def manage_announcements():
    if current_user.is_super_admin():
        announcements = Announcement.query.order_by(
            Announcement.is_pinned.desc(), 
            Announcement.created_at.desc()
        ).all()
    else:
        admin_course_ids = [c.id for c in current_user.managed_courses]
        announcements = Announcement.query.filter(
            or_(
                Announcement.course_id.in_(admin_course_ids),
                Announcement.course_id.is_(None)
            )
        ).order_by(
            Announcement.is_pinned.desc(), 
            Announcement.created_at.desc()
        ).all()
    
    return render_template('admin/manage_announcements.html', announcements=announcements)


@admin_bp.route('/announcements/create', methods=['GET', 'POST'])
@login_required
@admin_required
def post_announcement():
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        is_pinned = request.form.get('is_pinned') == 'on'
        course_id = request.form.get('course_id')
        
        if not title or not content:
            flash('Title and content are required.', 'error')
            return render_template('admin/post_announcement.html', courses=courses)
        
        announcement = Announcement(
            title=title,
            content=content,
            is_pinned=is_pinned,
            course_id=course_id if course_id else None,
            author_id=current_user.id
        )
        db.session.add(announcement)
        db.session.commit()
        
        flash('Announcement posted successfully!', 'success')
        return redirect(url_for('admin.manage_announcements'))
    
    return render_template('admin/post_announcement.html', courses=courses)


@admin_bp.route('/announcements/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    flash('Announcement deleted.', 'success')
    return redirect(url_for('admin.manage_announcements'))


@admin_bp.route('/announcements/<int:announcement_id>/toggle-pin', methods=['POST'])
@login_required
@admin_required
def toggle_pin_announcement(announcement_id):
    """Toggle pin status of an announcement"""
    announcement = Announcement.query.get_or_404(announcement_id)
    
    if not current_user.is_super_admin() and announcement.course_id and announcement.course not in current_user.managed_courses:
        flash('You do not have permission to modify this announcement.', 'error')
        return redirect(url_for('admin.manage_announcements'))
    
    announcement.is_pinned = not announcement.is_pinned
    announcement.updated_at = datetime.utcnow()
    db.session.commit()
    
    status = 'pinned' if announcement.is_pinned else 'unpinned'
    flash(f'Announcement {status} successfully!', 'success')
    return redirect(url_for('admin.manage_announcements'))


# ============================================================================
# TAGS
# ============================================================================

@admin_bp.route('/tags')
@login_required
@admin_required
def manage_tags():
    tags = Tag.query.all()
    return render_template('admin/manage_tags.html', tags=tags)


@admin_bp.route('/tags/create', methods=['POST'])
@login_required
@admin_required
def create_tag():
    name = request.form.get('name')
    if not name:
        flash('Tag name is required.', 'error')
        return redirect(url_for('admin.manage_tags'))
    
    if Tag.query.filter_by(name=name).first():
        flash('Tag already exists.', 'error')
        return redirect(url_for('admin.manage_tags'))
    
    tag = Tag(name=name)
    db.session.add(tag)
    db.session.commit()
    flash(f'Tag "{name}" created!', 'success')
    return redirect(url_for('admin.manage_tags'))


@admin_bp.route('/tags/<int:tag_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    flash(f'Tag "{tag.name}" deleted.', 'success')
    return redirect(url_for('admin.manage_tags'))


# ============================================================================
# EXPORT
# ============================================================================

@admin_bp.route('/export')
@login_required
@admin_required
def export_page():
    return render_template('admin/export.html')


# ============================================================================
# RECENT ACTIVITY
# ============================================================================

@admin_bp.route('/recent-activity')
@login_required
@admin_required
def recent_activity():
    activities = []
    
    notes = Note.query.order_by(Note.created_at.desc()).limit(20).all()
    for note in notes:
        activities.append({
            'type': 'note',
            'action': f'Created note: "{note.title}"',
            'created_at': note.created_at,
            'user': note.author.username if note.author else 'Unknown',
            'url': url_for('note.edit_note', note_id=note.id) if note.id else None
        })
    
    quizzes = QuizGroup.query.order_by(QuizGroup.created_at.desc()).limit(20).all()
    for quiz in quizzes:
        activities.append({
            'type': 'quiz',
            'action': f'Created quiz: "{quiz.title}"',
            'created_at': quiz.created_at,
            'user': quiz.author.username if quiz.author else 'Unknown'
        })
    
    activities.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('admin/recent_activity.html', activities=activities[:50])


# ============================================================================
# ANALYTICS
# ============================================================================

@admin_bp.route('/course-analytics')
@login_required
@admin_required
def course_analytics():
    if current_user.is_super_admin():
        courses = Course.query.all()
    else:
        courses = current_user.managed_courses
    
    course_data = []
    for course in courses:
        total_students = CourseEnrollment.query.filter_by(
            course_id=course.id, status='approved'
        ).count()
        
        course_data.append({
            'course': course,
            'total_students': total_students,
            'notes_count': len(course.notes),
            'quizzes_count': len(course.quiz_groups),
            'assignments_count': len(course.assignments)
        })
    
    return render_template('admin/course_analytics.html', course_data=course_data)


# ============================================================================
# BULK ACTIONS
# ============================================================================

@admin_bp.route('/bulk-actions', methods=['GET', 'POST'])
@login_required
@admin_required
def bulk_actions():
    students = User.query.filter_by(role='student').all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        student_ids = request.form.getlist('student_ids')
        
        if not student_ids:
            flash('No students selected.', 'warning')
            return redirect(url_for('admin.bulk_actions'))
        
        if action == 'approve':
            for sid in student_ids:
                student = User.query.get(sid)
                if student:
                    student.is_approved = True
            db.session.commit()
            flash(f'{len(student_ids)} students approved.', 'success')
        
        elif action == 'delete':
            if not current_user.is_super_admin():
                flash('Only super admin can delete students.', 'error')
                return redirect(url_for('admin.bulk_actions'))
            
            for sid in student_ids:
                student = User.query.get(sid)
                if student:
                    db.session.delete(student)
            db.session.commit()
            flash(f'{len(student_ids)} students deleted.', 'success')
        
        return redirect(url_for('admin.bulk_actions'))
    
    return render_template('admin/bulk_actions.html', students=students)


# ============================================================================
# ADMIN MESSAGES
# ============================================================================

@admin_bp.route('/messages')
@login_required
@admin_required
def admin_messages():
    students = User.query.filter_by(role='student').all()
    return render_template('admin/admin_messages.html', students=students)


# ============================================================================
# STUDENT DIRECTORY
# ============================================================================

@admin_bp.route('/student-directory')
@login_required
@admin_required
def student_directory():
    """View all students in a directory format"""
    # Get filter parameters
    course_id = request.args.get('course_id', type=int)
    search = request.args.get('search', '')
    
    # Base query
    if current_user.is_super_admin():
        students_query = User.query.filter_by(role='student')
        courses = Course.query.all()
    else:
        course_ids = [c.id for c in current_user.managed_courses]
        students_query = User.query.filter(
            User.role == 'student',
            User.id.in_(
                db.session.query(CourseEnrollment.student_id).filter(
                    CourseEnrollment.course_id.in_(course_ids)
                )
            )
        )
        courses = current_user.managed_courses
    
    # Apply course filter
    if course_id and course_id > 0:
        course = Course.query.get(course_id)
        if course:
            student_ids = db.session.query(CourseEnrollment.student_id).filter(
                CourseEnrollment.course_id == course.id,
                CourseEnrollment.status == 'approved'
            ).distinct().all()
            student_ids = [s[0] for s in student_ids]
            if student_ids:
                students_query = students_query.filter(User.id.in_(student_ids))
            else:
                students_query = students_query.filter(User.id.in_([-1]))
    
    # Apply search filter
    if search:
        search_term = f"%{search}%"
        students_query = students_query.filter(
            db.or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    # Get students with their enrollments
    students = students_query.order_by(User.created_at.desc()).all()
    
    # Prepare student data with course information
    student_data = []
    for student in students:
        enrollments = CourseEnrollment.query.filter_by(
            student_id=student.id,
            status='approved'
        ).all()
        
        student_data.append({
            'student': student,
            'enrolled_courses': [e.course for e in enrollments],
            'course_count': len(enrollments),
            'has_profile_pic': bool(student.profile_picture),
            'status': 'Active' if student.is_approved else 'Pending',
            'is_suspended': student.is_suspended
        })
    
    return render_template('admin/student_directory.html',
                         student_data=student_data,
                         courses=courses,
                         selected_course_id=course_id,
                         search_query=search,
                         total_students=len(students))


# ============================================================================
# SYSTEM LOGS
# ============================================================================

@admin_bp.route('/system-logs')
@login_required
@super_admin_required
def system_logs():
    return render_template('admin/system_logs.html')


# ============================================================================
# BACKUP & RESTORE
# ============================================================================

@admin_bp.route('/backup-restore')
@login_required
@super_admin_required
def backup_restore():
    return render_template('admin/backup_restore.html')


# ============================================================================
# EMAIL TEMPLATES
# ============================================================================

@admin_bp.route('/email-templates')
@login_required
@super_admin_required
def email_templates():
    return render_template('admin/email_templates.html')


# ============================================================================
# ADMIN MANAGEMENT (Super Admin)
# ============================================================================

@admin_bp.route('/admins')
@login_required
@super_admin_required
def manage_admins():
    admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    return render_template('admin/manage_admins.html', admins=admins)


@admin_bp.route('/admins/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_admin():
    courses = Course.query.all()
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        assigned_courses = request.form.getlist('courses')
        
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('admin/create_admin.html', courses=courses)
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('admin/create_admin.html', courses=courses)
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('admin/create_admin.html', courses=courses)
        
        admin = User(
            username=username,
            email=email,
            role='admin',
            is_approved=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()
        
        for course_id in assigned_courses:
            course = Course.query.get(course_id)
            if course:
                admin.managed_courses.append(course)
        
        db.session.commit()
        flash(f'Admin {username} created!', 'success')
        return redirect(url_for('admin.manage_admins'))
    
    return render_template('admin/create_admin.html', courses=courses)


@admin_bp.route('/admins/<int:admin_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_admin(admin_id):
    admin = User.query.get_or_404(admin_id)
    courses = Course.query.all()
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        assigned_courses = request.form.getlist('courses')
        
        admin.username = username
        admin.email = email
        admin.managed_courses = []
        
        for course_id in assigned_courses:
            course = Course.query.get(course_id)
            if course:
                admin.managed_courses.append(course)
        
        db.session.commit()
        flash(f'Admin {username} updated!', 'success')
        return redirect(url_for('admin.manage_admins'))
    
    return render_template('admin/edit_admin.html', admin=admin, courses=courses)


@admin_bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_admin(admin_id):
    admin = User.query.get_or_404(admin_id)
    if admin.is_super_admin():
        flash('Cannot delete super admin.', 'error')
        return redirect(url_for('admin.manage_admins'))
    
    db.session.delete(admin)
    db.session.commit()
    flash(f'Admin {admin.username} deleted.', 'success')
    return redirect(url_for('admin.manage_admins'))