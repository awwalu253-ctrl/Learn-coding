# backend/routes/dashboard.py
from flask import Blueprint, redirect, url_for
from flask_login import login_required, current_user

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    if not current_user.is_approved:
        return redirect(url_for('auth.pending_approval'))
    
    return redirect(url_for('student.dashboard'))