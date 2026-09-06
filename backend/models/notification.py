# backend/models/notification.py
from datetime import datetime
from ..extensions import db

class Notification(db.Model):
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')
    link = db.Column(db.String(500), nullable=True)
    icon = db.Column(db.String(50), default='fa-bell')
    icon_color = db.Column(db.String(20), default='gold')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # This creates the backref to User.notifications
    user = db.relationship('User', backref='notifications', foreign_keys=[user_id])
    
    def __repr__(self):
        return f'<Notification {self.id} - {self.user_id}>'

class RejectionMessage(db.Model):
    __tablename__ = 'rejection_message'
    __table_args__ = (
        db.Index('idx_rejection_student', 'student_id'),
        db.Index('idx_rejection_course', 'course_id'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    student = db.relationship('User', backref='rejections', foreign_keys=[student_id])
    course = db.relationship('Course', backref='rejections', foreign_keys=[course_id])
    
    def __repr__(self):
        return f'<RejectionMessage {self.id}>'