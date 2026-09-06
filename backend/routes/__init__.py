# backend/routes/__init__.py
from .auth import auth_bp
from .dashboard import dashboard_bp
from .student import student_bp
from .admin import admin_bp
from .course import course_bp
from .note import note_bp
from .quiz import quiz_bp  # Make sure this is imported
from .assignment import assignment_bp
from .leaderboard import leaderboard_bp
from .settings import settings_bp
from .api import api_bp