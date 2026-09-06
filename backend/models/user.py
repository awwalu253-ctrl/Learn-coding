# backend/models/user.py
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db
from .notification import Notification

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student')
    is_approved = db.Column(db.Boolean, default=False)
    is_suspended = db.Column(db.Boolean, default=False)
    suspension_reason = db.Column(db.Text, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    dob = db.Column(db.DateTime, nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    dark_mode = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    managed_courses = db.relationship('Course', secondary='admin_course', backref='admins')
    notes_read = db.relationship('StudentProgress', backref='student', lazy=True)
    quiz_answers = db.relationship('QuizAnswer', backref='student', lazy=True)
    submissions = db.relationship('AssignmentSubmission', backref='student', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role in ['admin', 'super_admin']
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def is_active(self):
        return not self.is_suspended
    
    def get_unread_notifications_count(self):
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()
    
    def get_recent_notifications(self, limit=10):
        return Notification.query.filter_by(user_id=self.id).order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
    
    # ============================================
    # COURSE ENROLLMENT METHODS
    # ============================================
    # Note: CourseEnrollment is defined in the same file below
    # No need to import it
    
    def get_enrolled_courses(self):
        """Get all courses the user is enrolled in (approved)"""
        # CourseEnrollment is defined in this same file
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.id, 
            status='approved'
        ).all()
        return [e.course for e in enrollments]
    
    def get_pending_courses(self):
        """Get all courses the user has pending enrollment requests for"""
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.id, 
            status='pending'
        ).all()
        return [e.course for e in enrollments]
    
    def get_rejected_courses(self):
        """Get all courses the user was rejected from"""
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.id, 
            status='rejected'
        ).all()
        return [e.course for e in enrollments]
    
    def is_enrolled_in_course(self, course_id):
        """Check if user is enrolled in a specific course"""
        enrollment = CourseEnrollment.query.filter_by(
            student_id=self.id,
            course_id=course_id,
            status='approved'
        ).first()
        return enrollment is not None
    
    def has_pending_request_for_course(self, course_id):
        """Check if user has a pending request for a course"""
        enrollment = CourseEnrollment.query.filter_by(
            student_id=self.id,
            course_id=course_id,
            status='pending'
        ).first()
        return enrollment is not None
    
    def get_course_status(self, course_id):
        """Get the status of a course enrollment"""
        enrollment = CourseEnrollment.query.filter_by(
            student_id=self.id,
            course_id=course_id
        ).first()
        return enrollment.status if enrollment else None
    
    def get_courses(self):
        """Get all courses the user has access to (based on role)"""
        if self.role == 'super_admin':
            from .course import Course
            return Course.query.all()
        elif self.role == 'admin':
            return self.managed_courses
        else:
            return self.get_enrolled_courses()
    
    def __repr__(self):
        return f'<User {self.username}>'


# Admin-Course association table
admin_course = db.Table('admin_course',
    db.Column('admin_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'))
)


class CourseEnrollment(db.Model):
    __tablename__ = 'course_enrollment'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    
    student = db.relationship('User', backref='enrollments', foreign_keys=[student_id])
    course = db.relationship('Course', backref='enrollments')
    
    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', name='unique_student_course_enrollment'),
        db.Index('idx_enrollment_student_course', 'student_id', 'course_id'),
        db.Index('idx_enrollment_status', 'status'),
    )
    
    def __repr__(self):
        return f'<CourseEnrollment {self.student_id} - {self.course_id} ({self.status})>'


def create_initial_admin():
    """Create initial admin user if none exists"""
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@awwaludevs.com',
            role='super_admin',
            is_approved=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin created: admin / admin123")
    else:
        # Ensure admin has correct role and is approved
        if admin.role != 'super_admin':
            admin.role = 'super_admin'
        admin.is_approved = True
        db.session.commit()