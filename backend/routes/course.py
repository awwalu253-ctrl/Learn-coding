# backend/routes/course.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from ..extensions import db
from ..models.course import Course
from ..models.note import Note
from ..models.user import User, CourseEnrollment
from ..models.quiz import QuizGroup
from ..models.assignment import Assignment
from ..models.notification import RejectionMessage  # ✅ FIXED: Import from notification
from ..utils.decorators import student_required, admin_required

course_bp = Blueprint('course', __name__)


@course_bp.route('/<int:course_id>')
@login_required
def view(course_id):
    """View a single course"""
    course = Course.query.get_or_404(course_id)
    
    if current_user.is_admin():
        notes = Note.query.filter_by(course_id=course_id).order_by(Note.created_at.desc()).all()
        quizzes = QuizGroup.query.filter_by(course_id=course_id).all()
        assignments = Assignment.query.filter_by(course_id=course_id).all()
        progress = 0
        return render_template('course/view.html', 
                             course=course, 
                             notes=notes, 
                             quizzes=quizzes, 
                             assignments=assignments,
                             progress=progress)
    
    if not current_user.is_enrolled_in_course(course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student.courses'))
    
    notes = Note.query.filter_by(course_id=course_id).order_by(Note.created_at.desc()).all()
    quizzes = QuizGroup.query.filter_by(course_id=course_id).all()
    assignments = Assignment.query.filter_by(course_id=course_id).all()
    progress = course.get_progress_for_student(current_user.id)
    
    return render_template('course/view.html', 
                         course=course, 
                         notes=notes, 
                         quizzes=quizzes, 
                         assignments=assignments,
                         progress=progress)


@course_bp.route('/<int:course_id>/request', methods=['POST'])
@login_required
def request_course(course_id):
    """Request access to a course"""
    course = Course.query.get_or_404(course_id)
    
    if current_user.is_admin():
        flash('Admins cannot request courses.', 'warning')
        return redirect(url_for('student.courses'))
    
    # Check if already enrolled or pending
    existing = CourseEnrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course_id
    ).first()
    
    if existing:
        if existing.status == 'approved':
            flash('You are already enrolled in this course.', 'info')
        elif existing.status == 'pending':
            flash('Your request for this course is pending approval.', 'warning')
        elif existing.status == 'rejected':
            flash('Your request for this course was previously rejected.', 'error')
        return redirect(url_for('student.courses'))
    
    enrollment = CourseEnrollment(
        student_id=current_user.id,
        course_id=course_id,
        status='pending'
    )
    db.session.add(enrollment)
    db.session.commit()
    
    # Send notification to admins
    from ..services.notification_service import create_notification
    admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    for admin in admins:
        create_notification(
            user_id=admin.id,
            title='📋 New Course Request',
            message=f'{current_user.username} requested access to "{course.name}"',
            type='info',
            link=url_for('admin.manage_students'),
            icon='fa-book-open',
            icon_color='gold'
        )
    
    flash(f'Request sent for {course.name}. Waiting for admin approval.', 'success')
    return redirect(url_for('student.courses'))


@course_bp.route('/<int:course_id>/reapply', methods=['POST'])
@login_required
def reapply_course(course_id):
    """Re-apply for a rejected course"""
    course = Course.query.get_or_404(course_id)
    
    if current_user.is_admin():
        flash('Admins cannot request courses.', 'warning')
        return redirect(url_for('student.courses'))
    
    enrollment = CourseEnrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course_id,
        status='rejected'
    ).first()
    
    if not enrollment:
        flash('You have not been rejected from this course.', 'info')
        return redirect(url_for('student.courses'))
    
    # Update enrollment status back to pending
    enrollment.status = 'pending'
    enrollment.rejected_at = None
    enrollment.rejection_reason = None
    
    # Delete rejection message
    RejectionMessage.query.filter_by(
        student_id=current_user.id,
        course_id=course_id
    ).delete()
    
    db.session.commit()
    
    # Send notification to admins
    from ..services.notification_service import create_notification
    admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    for admin in admins:
        create_notification(
            user_id=admin.id,
            title='🔄 Course Re-application',
            message=f'{current_user.username} re-applied for "{course.name}" after rejection',
            type='info',
            link=url_for('admin.manage_students'),
            icon='fa-redo',
            icon_color='gold'
        )
    
    flash(f'You have re-applied for {course.name}. Waiting for admin approval.', 'success')
    return redirect(url_for('student.courses'))


@course_bp.route('/<int:course_id>/note/<int:note_id>')
@login_required
def view_note(course_id, note_id):
    """View a specific note within a course"""
    course = Course.query.get_or_404(course_id)
    note = Note.query.get_or_404(note_id)
    
    if current_user.is_admin():
        return render_template('course/note.html', course=course, note=note)
    
    if not current_user.is_enrolled_in_course(course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student.courses'))
    
    # Mark as read
    from ..models.note import StudentProgress
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id,
        note_id=note.id
    ).first()
    
    if not progress:
        progress = StudentProgress(
            student_id=current_user.id,
            note_id=note.id,
            course_id=course_id,
            is_read=True,
            read_at=datetime.utcnow()
        )
        db.session.add(progress)
    elif not progress.is_read:
        progress.is_read = True
        progress.read_at = datetime.utcnow()
    
    db.session.commit()
    
    return render_template('course/note.html', course=course, note=note)


@course_bp.route('/<int:course_id>/quiz/<int:quiz_id>')
@login_required
def view_quiz(course_id, quiz_id):
    """View a specific quiz within a course"""
    course = Course.query.get_or_404(course_id)
    quiz = QuizGroup.query.get_or_404(quiz_id)
    
    if current_user.is_admin():
        return render_template('course/quiz.html', course=course, quiz=quiz)
    
    if not current_user.is_enrolled_in_course(course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student.courses'))
    
    return render_template('course/quiz.html', course=course, quiz=quiz)


@course_bp.route('/<int:course_id>/assignment/<int:assignment_id>')
@login_required
def view_assignment(course_id, assignment_id):
    """View a specific assignment within a course"""
    course = Course.query.get_or_404(course_id)
    assignment = Assignment.query.get_or_404(assignment_id)
    
    if current_user.is_admin():
        return render_template('course/assignment.html', course=course, assignment=assignment)
    
    if not current_user.is_enrolled_in_course(course_id):
        flash('You are not enrolled in this course.', 'error')
        return redirect(url_for('student.courses'))
    
    submission = assignment.get_submission_for_student(current_user.id)
    
    return render_template('course/assignment.html', 
                         course=course, 
                         assignment=assignment,
                         submission=submission)