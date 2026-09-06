# backend/__init__.py
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_cors import CORS
from flask_caching import Cache
import os
import logging
from datetime import datetime

from .config import Config
from .extensions import db, login_manager, migrate, cache

# Import models so they're registered with SQLAlchemy
from .models import User, Course, Note, Tag, StudentProgress
from .models import QuizGroup, QuizQuestion, QuizAnswer
from .models import Assignment, AssignmentSubmission
from .models import Notification, RejectionMessage
from .models import SystemSetting, Backup, EmailTemplate

# Try to import Announcement
try:
    from .models.announcement import Announcement
except ImportError:
    from datetime import datetime
    class Announcement(db.Model):
        __tablename__ = 'announcement'
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(200), nullable=False)
        content = db.Column(db.Text, nullable=False)
        is_pinned = db.Column(db.Boolean, default=False)
        course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
        
        author = db.relationship('User', backref='announcements')
        course = db.relationship('Course', backref='announcements')

from .utils.timezone import utc_to_local, format_relative_time, format_local_time, get_system_timezone

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
    
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    cache.init_app(app)
    
    # ============================================
    # USER LOADER FOR FLASK-LOGIN
    # ============================================
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except:
            return None
    
    @login_manager.request_loader
    def load_user_from_request(request):
        user_id = request.headers.get('X-User-ID')
        if user_id:
            try:
                return User.query.get(int(user_id))
            except:
                pass
        return None
    
    # Import and register middleware
    try:
        from .middleware.maintenance import maintenance_check
        app.before_request(maintenance_check)
    except:
        pass
    
    # Register blueprints (routes)
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.student import student_bp
    from .routes.admin import admin_bp
    from .routes.course import course_bp
    from .routes.note import note_bp
    from .routes.quiz import quiz_bp
    from .routes.assignment import assignment_bp
    from .routes.leaderboard import leaderboard_bp
    from .routes.settings import settings_bp
    from .routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(course_bp, url_prefix='/course')
    app.register_blueprint(note_bp, url_prefix='/note')
    app.register_blueprint(quiz_bp, url_prefix='/quiz')
    app.register_blueprint(assignment_bp, url_prefix='/assignment')
    app.register_blueprint(leaderboard_bp, url_prefix='/leaderboard')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # ============================================
    # ROOT ROUTE - FIXES THE "NOT FOUND" ERROR
    # ============================================
    @app.route('/')
    def home():
        if current_user.is_authenticated:
            if current_user.is_admin():
                return redirect(url_for('admin.dashboard'))
            elif current_user.is_approved:
                return redirect(url_for('student.dashboard'))
            else:
                return redirect(url_for('auth.pending_approval'))
        return redirect(url_for('auth.login'))
    
    # ============================================
    # CONTEXT PROCESSOR
    # ============================================
    @app.context_processor
    def inject_user():
        from .services.user_service import UserService
        from .services.admin_service import AdminService
        
        # Get student count
        try:
            student_count = User.query.filter_by(role='student').count()
        except:
            student_count = 0
        
        return {
            'current_user': current_user,
            'now': datetime.utcnow(),
            'get_courses': UserService.get_user_courses,
            'is_approved': UserService.is_user_approved,
            'site_name': 'A-Portal LMS',
            'site_description': 'Learning Management System',
            'get_setting': AdminService.get_setting,
            'get_bool_setting': AdminService.get_bool_setting,
            'utc_to_local': utc_to_local,
            'format_relative_time': format_relative_time,
            'format_local_time': format_local_time,
            'get_system_timezone': get_system_timezone,
            'total_students': UserService.get_total_students(),
            'total_courses': AdminService.get_total_courses(),
            'student_count': student_count,
        }
    
    # Register custom Jinja2 filters
    @app.template_filter('time_ago')
    def time_ago_filter(dt):
        return format_relative_time(dt)
    
    @app.template_filter('local_time')
    def local_time_filter(dt, format_str='%b %d, %Y at %I:%M %p'):
        return format_local_time(dt, format_str)
    
    @app.template_filter('local_date')
    def local_date_filter(dt):
        return format_local_time(dt, '%b %d, %Y')
    
    @app.template_filter('zfill')
    def zfill_filter(value, width):
        return str(value).zfill(width)
    
    # Register error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def server_error(error):
        return render_template('500.html'), 500
    
    # ============================================
    # INITIALIZE DATABASE
    # ============================================
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created")
        except Exception as e:
            print(f"⚠️ Database creation warning: {e}")
            db.session.rollback()
        
        # Run column migration - FIXED: Handle import gracefully
        try:
            from .config import ensure_columns
            ensure_columns()
            print("✅ Column migration complete")
        except ImportError:
            print("⚠️ ensure_columns not found in config.py - skipping")
        except Exception as e:
            print(f"⚠️ Column migration warning: {e}")
            db.session.rollback()
        
        try:
            from .models.system import init_default_settings
            init_default_settings()
            print("✅ Settings initialized")
        except Exception as e:
            print(f"⚠️ Settings initialization warning: {e}")
            db.session.rollback()
        
        try:
            from .models.user import create_initial_admin
            create_initial_admin()
            print("✅ Admin user handled")
        except Exception as e:
            print(f"⚠️ Admin creation warning: {e}")
            db.session.rollback()
    
    return app