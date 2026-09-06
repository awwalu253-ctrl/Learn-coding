# backend/routes/settings.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.system import SystemSetting, save_setting, get_setting, get_all_settings, get_bool_setting
from ..utils.decorators import super_admin_required

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/system', methods=['GET', 'POST'])
@login_required
@super_admin_required
def system_settings():
    if request.method == 'POST':
        try:
            # General settings
            save_setting('site_name', request.form.get('site_name', 'A-Portal LMS'), 'string', 'Site name', 'general')
            save_setting('site_description', request.form.get('site_description', 'Learning Management System'), 'string', 'Site description', 'general')
            save_setting('maintenance_mode', request.form.get('maintenance_mode') == 'on', 'boolean', 'Maintenance mode', 'general')
            save_setting('timezone', request.form.get('timezone', 'UTC'), 'string', 'System timezone', 'general')
            
            # Student settings
            save_setting('auto_approve_students', request.form.get('auto_approve_students') == 'on', 'boolean', 'Auto approve students', 'student')
            save_setting('max_courses_per_student', int(request.form.get('max_courses_per_student', 10)), 'integer', 'Max courses per student', 'student')
            save_setting('allow_reapplications', request.form.get('allow_reapplications') == 'on', 'boolean', 'Allow re-applications', 'student')
            save_setting('require_phone_number', request.form.get('require_phone_number') == 'on', 'boolean', 'Require phone number', 'student')
            
            # Security settings
            save_setting('session_timeout', int(request.form.get('session_timeout', 60)), 'integer', 'Session timeout in minutes', 'security')
            save_setting('max_login_attempts', int(request.form.get('max_login_attempts', 5)), 'integer', 'Max login attempts', 'security')
            save_setting('force_ssl', request.form.get('force_ssl') == 'on', 'boolean', 'Force SSL', 'security')
            
            # Content settings
            save_setting('max_file_upload_size', int(request.form.get('max_file_upload_size', 16)), 'integer', 'Max file upload size (MB)', 'content')
            save_setting('allowed_file_types', request.form.get('allowed_file_types', 'pdf,png,jpg,jpeg,gif,doc,docx,txt,zip'), 'string', 'Allowed file types', 'content')
            
            # Notification settings
            save_setting('email_notifications', request.form.get('email_notifications') == 'on', 'boolean', 'Email notifications', 'notification')
            save_setting('push_notifications', request.form.get('push_notifications') == 'on', 'boolean', 'Push notifications', 'notification')
            save_setting('assignment_reminders', request.form.get('assignment_reminders') == 'on', 'boolean', 'Assignment reminders', 'notification')
            save_setting('reminder_days_before', int(request.form.get('reminder_days_before', 3)), 'integer', 'Days before due date', 'notification')
            
            db.session.commit()
            flash('✅ Settings saved successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving settings: {str(e)}', 'error')
        
        return redirect(url_for('settings.system_settings'))
    
    settings = get_all_settings()
    return render_template('admin/system_settings.html', settings=settings)

@settings_bp.route('/toggle-dark-mode', methods=['POST'])
@login_required
def toggle_dark_mode():
    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()
    return jsonify({'dark_mode': current_user.dark_mode})

@settings_bp.route('/get-setting/<key>')
@login_required
def get_setting_api(key):
    value = get_setting(key)
    return jsonify({'key': key, 'value': value})

@settings_bp.route('/maintenance/toggle', methods=['POST'])
@login_required
@super_admin_required
def toggle_maintenance():
    current_mode = get_bool_setting('maintenance_mode', False)
    save_setting('maintenance_mode', str(not current_mode), 'boolean', 'Maintenance mode', 'general')
    return jsonify({'maintenance_mode': not current_mode})