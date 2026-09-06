# backend/models/system.py
from datetime import datetime
from ..extensions import db

class SystemSetting(db.Model):
    __tablename__ = 'system_setting'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    setting_type = db.Column(db.String(50), default='string')
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='general')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Backup(db.Model):
    __tablename__ = 'backup'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    backup_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    size = db.Column(db.String(50))
    record_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String(80))

class EmailTemplate(db.Model):
    __tablename__ = 'email_template'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_setting(key, default=None):
    """Get a setting value by key"""
    try:
        setting = SystemSetting.query.filter_by(key=key).first()
        if setting:
            value = setting.value
            if value.lower() == 'true':
                return True
            elif value.lower() == 'false':
                return False
            try:
                if value.isdigit():
                    return int(value)
            except:
                pass
            return value
        return default
    except Exception as e:
        return default

def get_all_settings():
    """Get all settings as a dictionary"""
    settings = {}
    try:
        all_settings = SystemSetting.query.all()
        for setting in all_settings:
            value = setting.value
            if value.lower() == 'true':
                settings[setting.key] = True
            elif value.lower() == 'false':
                settings[setting.key] = False
            else:
                try:
                    if value.isdigit():
                        settings[setting.key] = int(value)
                    else:
                        settings[setting.key] = value
                except:
                    settings[setting.key] = value
        return settings
    except Exception as e:
        return {}

def save_setting(key, value, setting_type='string', description='', category='general'):
    """Save or update a setting"""
    try:
        setting = SystemSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value) if value is not None else ''
            setting.setting_type = setting_type
            setting.description = description
            setting.category = category
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSetting(
                key=key,
                value=str(value) if value is not None else '',
                setting_type=setting_type,
                description=description,
                category=category
            )
            db.session.add(setting)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False

def get_bool_setting(key, default=False):
    """Get a boolean setting"""
    value = get_setting(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == 'true'
    return bool(value)

def get_int_setting(key, default=0):
    """Get an integer setting"""
    value = get_setting(key, default)
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def get_str_setting(key, default=''):
    """Get a string setting"""
    value = get_setting(key, default)
    return str(value) if value is not None else ''

def init_default_settings():
    """Initialize default settings if they don't exist"""
    defaults = {
        'site_name': ('A-Portal LMS', 'string', 'general'),
        'site_description': ('Learning Management System', 'string', 'general'),
        'default_language': ('en', 'string', 'general'),
        'maintenance_mode': ('False', 'boolean', 'general'),
        'timezone': ('UTC', 'string', 'general'),
        'auto_approve_students': ('False', 'boolean', 'student'),
        'max_courses_per_student': ('10', 'integer', 'student'),
        'allow_reapplications': ('True', 'boolean', 'student'),
        'require_phone_number': ('True', 'boolean', 'student'),
        'student_registration_enabled': ('True', 'boolean', 'student'),
        'session_timeout': ('60', 'integer', 'security'),
        'require_email_verification': ('False', 'boolean', 'security'),
        'max_login_attempts': ('5', 'integer', 'security'),
        'lockout_duration': ('30', 'integer', 'security'),
        'force_ssl': ('True', 'boolean', 'security'),
        'max_file_upload_size': ('16', 'integer', 'content'),
        'allowed_file_types': ('pdf,png,jpg,jpeg,gif,doc,docx,txt,zip', 'string', 'content'),
        'enable_comments': ('False', 'boolean', 'content'),
        'enable_ratings': ('True', 'boolean', 'content'),
        'email_notifications': ('True', 'boolean', 'notification'),
        'push_notifications': ('True', 'boolean', 'notification'),
        'assignment_reminders': ('True', 'boolean', 'notification'),
        'reminder_days_before': ('3', 'integer', 'notification'),
    }
    
    for key, (value, setting_type, category) in defaults.items():
        if not SystemSetting.query.filter_by(key=key).first():
            setting = SystemSetting(
                key=key,
                value=value,
                setting_type=setting_type,
                category=category
            )
            db.session.add(setting)
    
    db.session.commit()