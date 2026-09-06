# backend/utils/decorators.py
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'super_admin']:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'super_admin':
            flash('Super admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login'))
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        if current_user.is_suspended:
            flash('Your account is suspended.', 'error')
            return redirect(url_for('auth.logout'))
        if not current_user.is_approved:
            flash('Your account is pending approval.', 'warning')
            return redirect(url_for('student.pending_approval'))
        return f(*args, **kwargs)
    return decorated_function