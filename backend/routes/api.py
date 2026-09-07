# backend/routes/api.py
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models.notification import Notification

api_bp = Blueprint('api', __name__)

@api_bp.after_request
def after_request(response):
    """Add CORS headers to all API responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@api_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'message': 'API is running'})

@api_bp.route('/notifications')
@login_required
def get_notifications():
    """Get unread notifications for the current user"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    data = []
    for notif in notifications:
        data.append({
            'id': notif.id,
            'type': notif.type,
            'title': notif.title,
            'message': notif.message,
            'url': notif.link or '#',
            'icon': notif.icon,
            'icon_color': notif.icon_color,
            'created_at': notif.created_at.isoformat() if notif.created_at else None,
            'is_read': notif.is_read
        })
    
    return jsonify(data)

@api_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    """Mark all notifications as read for the current user"""
    try:
        current_app.logger.info(f"Marking notifications as read for user: {current_user.id}")
        
        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).all()
        
        count = len(notifications)
        current_app.logger.info(f"Found {count} unread notifications")
        
        for notif in notifications:
            notif.is_read = True
        
        db.session.commit()
        
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking notifications as read: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/notifications/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_single_notification_read(notification_id):
    """Mark a single notification as read"""
    try:
        notification = Notification.query.get_or_404(notification_id)
        
        if notification.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/notifications/unread-count')
@login_required
def get_unread_count():
    """Get the count of unread notifications"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    return jsonify({'unread_count': count})