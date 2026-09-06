# backend/services/user_service.py
from flask_login import current_user
from datetime import datetime
from ..extensions import db
from ..models.user import User

class UserService:
    @staticmethod
    def get_current_user():
        return current_user
    
    @staticmethod
    def get_current_time():
        return datetime.utcnow()
    
    @staticmethod
    def get_user_courses():
        if current_user.is_authenticated:
            return current_user.get_courses()
        return []
    
    @staticmethod
    def is_user_approved():
        if current_user.is_authenticated:
            return current_user.is_approved
        return False
    
    @staticmethod
    def get_total_students():
        try:
            return User.query.filter_by(role='student').count()
        except:
            return 0