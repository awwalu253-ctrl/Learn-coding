# backend/services/notification_service.py
from flask import url_for
from ..extensions import db
from ..models.notification import Notification
from ..models.user import User

def create_notification(user_id, title, message, type='info', link=None, icon='fa-bell', icon_color='gold'):
    """Create a notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        link=link,
        icon=icon,
        icon_color=icon_color
    )
    db.session.add(notification)
    db.session.commit()
    return notification


def notify_student_approved(student_id):
    """Notify student when their account is approved"""
    user = User.query.get(student_id)
    if user:
        create_notification(
            user_id=student_id,
            title='Account Approved! 🎉',
            message=f'Your account has been approved. You can now log in and access courses.',
            type='success',
            link=url_for('student.dashboard'),
            icon='fa-check-circle',
            icon_color='green'
        )


def notify_student_rejected(student_id, course_name, reason):
    """Notify student when they are rejected from a course"""
    create_notification(
        user_id=student_id,
        title='Course Request Rejected ❌',
        message=f'Your request for "{course_name}" has been rejected. Reason: {reason}',
        type='error',
        link=url_for('student.courses'),
        icon='fa-times-circle',
        icon_color='red'
    )


def notify_course_approved(student_id, course_name):
    """Notify student when they are approved for a course"""
    course = Course.query.filter_by(name=course_name).first()
    create_notification(
        user_id=student_id,
        title='Course Approved! ✅',
        message=f'You have been approved for "{course_name}". Start learning now!',
        type='success',
        link=url_for('course.view', course_id=course.id) if course else None,
        icon='fa-check-circle',
        icon_color='green'
    )


def notify_course_request(student_id, course_name):
    """Notify student when they request a course"""
    create_notification(
        user_id=student_id,
        title='Course Requested 📚',
        message=f'Your request for "{course_name}" has been sent. Waiting for admin approval.',
        type='info',
        link=url_for('student.courses'),
        icon='fa-clock',
        icon_color='gold'
    )


def notify_admin_course_request(admin_id, student_name, course_name):
    """Notify admin when a student requests a course"""
    create_notification(
        user_id=admin_id,
        title='New Course Request 📋',
        message=f'{student_name} has requested access to "{course_name}". Please review.',
        type='warning',
        link=url_for('admin.manage_students'),
        icon='fa-users',
        icon_color='orange'
    )


def notify_student_suspended(student_id, reason):
    """Notify student when they are suspended"""
    create_notification(
        user_id=student_id,
        title='Account Suspended ⛔',
        message=f'Your account has been suspended. Reason: {reason}',
        type='error',
        link=None,
        icon='fa-ban',
        icon_color='red'
    )


def notify_student_unsuspended(student_id):
    """Notify student when they are unsuspended"""
    create_notification(
        user_id=student_id,
        title='Account Restored ✅',
        message='Your account has been unsuspended. You can now log in and access courses.',
        type='success',
        link=url_for('auth.login'),
        icon='fa-check-circle',
        icon_color='green'
    )


def notify_admin_new_student(admin_id, student_name):
    """Notify admin when a new student registers"""
    create_notification(
        user_id=admin_id,
        title='📝 New Student Registration',
        message=f'New student "{student_name}" has registered and is pending approval.',
        type='info',
        link=url_for('admin.manage_students'),
        icon='fa-user-plus',
        icon_color='gold'
    )


def notify_admin_new_submission(admin_id, student_name, assignment_title, assignment_id):
    """Notify admin when a student submits an assignment"""
    create_notification(
        user_id=admin_id,
        title='📋 New Assignment Submission',
        message=f'{student_name} submitted "{assignment_title}"',
        type='info',
        link=url_for('assignment.view_submissions', assignment_id=assignment_id),
        icon='fa-tasks',
        icon_color='green'
    )


def notify_student_quiz_completed(student_id, quiz_title, score):
    """Notify student when they complete a quiz"""
    create_notification(
        user_id=student_id,
        title='📝 Quiz Completed!',
        message=f'You completed "{quiz_title}" with a score of {score}%',
        type='success',
        link=url_for('quiz.quiz_result', quiz_id=quiz_id),
        icon='fa-check-circle',
        icon_color='green'
    )


def notify_student_assignment_graded(student_id, assignment_title, score, max_score):
    """Notify student when an assignment is graded"""
    create_notification(
        user_id=student_id,
        title=f'📊 Assignment Graded: {assignment_title}',
        message=f'Your submission for "{assignment_title}" has been graded. Score: {score} out of {max_score}',
        type='success',
        link=url_for('student.assignments'),
        icon='fa-check-circle',
        icon_color='green'
    )


def notify_student_new_announcement(student_id, announcement_title, course_name):
    """Notify student when a new announcement is posted"""
    create_notification(
        user_id=student_id,
        title=f'📢 New Announcement: {announcement_title}',
        message=f'New announcement posted in {course_name}.',
        type='info',
        link=url_for('student.announcements'),
        icon='fa-bullhorn',
        icon_color='purple'
    )


def notify_student_new_note(student_id, note_title, course_name, note_id):
    """Notify student when a new note is posted"""
    create_notification(
        user_id=student_id,
        title=f'📝 New Note: {note_title}',
        message=f'A new note "{note_title}" has been posted in {course_name}.',
        type='info',
        link=url_for('note.view', note_id=note_id),
        icon='fa-file-alt',
        icon_color='blue'
    )


def notify_student_new_quiz(student_id, quiz_title, course_name):
    """Notify student when a new quiz is created"""
    create_notification(
        user_id=student_id,
        title=f'📝 New Quiz: {quiz_title}',
        message=f'A new quiz "{quiz_title}" is available in {course_name}.',
        type='info',
        link=url_for('quiz.student_quizzes'),
        icon='fa-puzzle-piece',
        icon_color='gold'
    )


def notify_student_new_assignment(student_id, assignment_title, course_name, due_date):
    """Notify student when a new assignment is created"""
    create_notification(
        user_id=student_id,
        title=f'📝 New Assignment: {assignment_title}',
        message=f'A new assignment "{assignment_title}" has been posted in {course_name}. Due: {due_date.strftime("%b %d, %Y")}',
        type='info',
        link=url_for('student.assignments'),
        icon='fa-tasks',
        icon_color='blue'
    )


def notify_student_announcement_deleted(student_id, announcement_title, course_name):
    """Notify student when an announcement is deleted"""
    create_notification(
        user_id=student_id,
        title=f'🗑️ Announcement Removed: {announcement_title}',
        message=f'The announcement "{announcement_title}" has been removed from {course_name}.',
        type='warning',
        link=url_for('student.announcements'),
        icon='fa-trash',
        icon_color='red'
    )


def notify_student_note_deleted(student_id, note_title, course_name):
    """Notify student when a note is deleted"""
    create_notification(
        user_id=student_id,
        title=f'🗑️ Note Removed: {note_title}',
        message=f'The note "{note_title}" has been removed from {course_name}.',
        type='warning',
        link=url_for('student.courses'),
        icon='fa-trash',
        icon_color='red'
    )


def notify_student_quiz_deleted(student_id, quiz_title, course_name):
    """Notify student when a quiz is deleted"""
    create_notification(
        user_id=student_id,
        title=f'🗑️ Quiz Removed: {quiz_title}',
        message=f'The quiz "{quiz_title}" has been removed from {course_name}.',
        type='warning',
        link=url_for('quiz.student_quizzes'),
        icon='fa-trash',
        icon_color='red'
    )


def notify_student_assignment_deleted(student_id, assignment_title, course_name):
    """Notify student when an assignment is deleted"""
    create_notification(
        user_id=student_id,
        title=f'🗑️ Assignment Removed: {assignment_title}',
        message=f'The assignment "{assignment_title}" has been removed from {course_name}.',
        type='warning',
        link=url_for('student.assignments'),
        icon='fa-trash',
        icon_color='red'
    )


def notify_student_profile_updated(student_id):
    """Notify student when their profile is updated"""
    create_notification(
        user_id=student_id,
        title='👤 Profile Updated',
        message='Your profile has been updated by an administrator.',
        type='info',
        link=url_for('auth.profile'),
        icon='fa-user-edit',
        icon_color='blue'
    )


def notify_student_password_reset(student_id, new_password):
    """Notify student when their password is reset"""
    create_notification(
        user_id=student_id,
        title='🔑 Password Reset',
        message=f'Your password has been reset by an administrator. New password: {new_password}',
        type='info',
        link=url_for('auth.login'),
        icon='fa-key',
        icon_color='gold'
    )