# backend/routes/api.py
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models.notification import Notification

api_bp = Blueprint('api', __name__)

@api_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'message': 'API is running'})

@api_bp.route('/notifications')
@login_required
def get_notifications():
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
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).all()
    
    for notif in notifications:
        notif.is_read = True
    
    db.session.commit()
    return jsonify({'success': True, 'count': len(notifications)})