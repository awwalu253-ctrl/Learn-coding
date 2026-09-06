# backend/services/admin_service.py
from ..models.system import get_setting, save_setting
from ..models.course import Course

class AdminService:
    @staticmethod
    def get_setting(key, default=None):
        return get_setting(key, default)
    
    @staticmethod
    def get_bool_setting(key, default=False):
        value = get_setting(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)
    
    @staticmethod
    def save_setting(key, value, setting_type='string', description='', category='general'):
        return save_setting(key, value, setting_type, description, category)
    
    @staticmethod
    def get_total_courses():
        try:
            return Course.query.count()
        except:
            return 0