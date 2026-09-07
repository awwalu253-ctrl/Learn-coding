# backend/models/__init__.py
from .user import User, CourseEnrollment, admin_course
from .course import Course
from .note import Note, StudentProgress, Tag
from .quiz import QuizGroup, QuizQuestion, QuizAnswer
from .assignment import Assignment, AssignmentSubmission
from .notification import Notification, RejectionMessage
from .system import SystemSetting, Backup, EmailTemplate
from .message import Message

# Try to import Announcement, if it exists
try:
    from .announcement import Announcement
except ImportError:
    from datetime import datetime
    from ..extensions import db
    
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