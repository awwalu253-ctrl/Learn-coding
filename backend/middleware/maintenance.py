# backend/middleware/maintenance.py
from flask import jsonify, render_template, request
from flask_login import current_user

def maintenance_check():
    # Skip for certain endpoints
    public_endpoints = ['static', 'auth.login', 'auth.logout', 'health', 'maintenance', 'api.health']
    
    # If endpoint is in public list, skip
    if request.endpoint in public_endpoints:
        return None
    
    # Check if user is authenticated before accessing current_user
    try:
        # Try to get current_user, but handle if not authenticated
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            if current_user.is_admin():
                return None
    except:
        # If there's any error accessing current_user, just continue
        pass
    
    # Check maintenance mode
    try:
        from ..models.system import get_bool_setting
        if get_bool_setting('maintenance_mode', False):
            if request.path.startswith('/api/'):
                return jsonify({
                    'error': 'Maintenance mode is enabled',
                    'status': 'maintenance'
                }), 503
            
            return render_template('maintenance.html'), 503
    except:
        # If there's an error checking, just continue
        pass
    
    return None