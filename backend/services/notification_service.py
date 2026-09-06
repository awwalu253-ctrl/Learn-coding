# backend/services/notification_service.py
from flask import url_for
from ..extensions import db
from ..models.notification import Notification
from ..models.user import User
from ..models.course import Course

def create_notification(user_id, title, message, type='info', link=None, icon='fa-bell', icon_color='gold'):
    """Create a notification for a user"""
    try:
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
    except Exception as e:
        print(f"Error creating notification: {e}")
        db.session.rollback()
        return None

def notify_course_approved(student_id, course_name):
    """Notify student when they are approved for a course"""
    try:
        # Get the course
        course = Course.query.filter_by(name=course_name).first()
        
        create_notification(
            user_id=student_id,
            title='✅ Course Approved!',
            message=f'You have been approved for "{course_name}". Start learning now!',
            type='success',
            link=url_for('course.view', course_id=course.id) if course else url_for('student.courses'),
            icon='fa-check-circle',
            icon_color='green'
        )
    except Exception as e:
        print(f"Error in notify_course_approved: {e}")
        # Fallback - create notification without course link
        try:
            create_notification(
                user_id=student_id,
                title='✅ Course Approved!',
                message=f'You have been approved for "{course_name}".',
                type='success',
                link=url_for('student.courses'),
                icon='fa-check-circle',
                icon_color='green'
            )
        except:
            pass

def notify_student_approved(student_id):
    """Notify student when their account is approved"""
    try:
        create_notification(
            user_id=student_id,
            title='Account Approved! 🎉',
            message=f'Your account has been approved. You can now log in and access courses.',
            type='success',
            link=url_for('student.dashboard'),
            icon='fa-check-circle',
            icon_color='green'
        )
    except Exception as e:
        print(f"Error in notify_student_approved: {e}")

def notify_student_rejected(student_id, course_name, reason):
    """Notify student when they are rejected from a course"""
    try:
        create_notification(
            user_id=student_id,
            title='Course Request Rejected ❌',
            message=f'Your request for "{course_name}" has been rejected. Reason: {reason}',
            type='error',
            link=url_for('student.courses'),
            icon='fa-times-circle',
            icon_color='red'
        )
    except Exception as e:
        print(f"Error in notify_student_rejected: {e}")

def notify_course_request(student_id, course_name):
    """Notify student when they request a course"""
    try:
        create_notification(
            user_id=student_id,
            title='Course Requested 📚',
            message=f'Your request for "{course_name}" has been sent. Waiting for admin approval.',
            type='info',
            link=url_for('student.courses'),
            icon='fa-clock',
            icon_color='gold'
        )
    except Exception as e:
        print(f"Error in notify_course_request: {e}")

def notify_admin_course_request(admin_id, student_name, course_name):
    """Notify admin when a student requests a course"""
    try:
        create_notification(
            user_id=admin_id,
            title='New Course Request 📋',
            message=f'{student_name} has requested access to "{course_name}". Please review.',
            type='warning',
            link=url_for('admin.manage_students'),
            icon='fa-users',
            icon_color='orange'
        )
    except Exception as e:
        print(f"Error in notify_admin_course_request: {e}")

def notify_student_suspended(student_id, reason):
    """Notify student when they are suspended"""
    try:
        create_notification(
            user_id=student_id,
            title='Account Suspended ⛔',
            message=f'Your account has been suspended. Reason: {reason}',
            type='error',
            link=None,
            icon='fa-ban',
            icon_color='red'
        )
    except Exception as e:
        print(f"Error in notify_student_suspended: {e}")

def notify_student_unsuspended(student_id):
    """Notify student when they are unsuspended"""
    try:
        create_notification(
            user_id=student_id,
            title='Account Restored ✅',
            message='Your account has been unsuspended. You can now log in and access courses.',
            type='success',
            link=url_for('auth.login'),
            icon='fa-check-circle',
            icon_color='green'
        )
    except Exception as e:
        print(f"Error in notify_student_unsuspended: {e}")

def notify_admin_new_student(admin_id, student_name):
    """Notify admin when a new student registers"""
    try:
        create_notification(
            user_id=admin_id,
            title='📝 New Student Registration',
            message=f'New student "{student_name}" has registered and is pending approval.',
            type='info',
            link=url_for('admin.manage_students'),
            icon='fa-user-plus',
            icon_color='gold'
        )
    except Exception as e:
        print(f"Error in notify_admin_new_student: {e}")

def notify_admin_new_submission(admin_id, student_name, assignment_title, assignment_id):
    """Notify admin when a student submits an assignment"""
    try:
        create_notification(
            user_id=admin_id,
            title='📋 New Assignment Submission',
            message=f'{student_name} submitted "{assignment_title}"',
            type='info',
            link=url_for('assignment.view_submissions', assignment_id=assignment_id),
            icon='fa-tasks',
            icon_color='green'
        )
    except Exception as e:
        print(f"Error in notify_admin_new_submission: {e}")