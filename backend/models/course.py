# backend/models/course.py
from datetime import datetime
from ..extensions import db

class Course(db.Model):
    __tablename__ = 'course'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    code = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    notes = db.relationship('Note', backref='course', lazy=True, cascade='all, delete-orphan')
    quiz_groups = db.relationship('QuizGroup', backref='course', lazy=True, cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', backref='course', lazy=True, cascade='all, delete-orphan')
    
    def get_progress_for_student(self, student_id):
        from .note import Note, StudentProgress
        total_notes = Note.query.filter_by(course_id=self.id).count()
        if total_notes == 0:
            return 0
        read_count = StudentProgress.query.filter_by(
            student_id=student_id, 
            course_id=self.id,
            is_read=True
        ).count()
        return int((read_count / total_notes) * 100)
    
    def get_enrolled_students(self):
        from .user import CourseEnrollment
        enrollments = CourseEnrollment.query.filter_by(
            course_id=self.id,
            status='approved'
        ).all()
        return [e.student for e in enrollments]
    
    def get_pending_students(self):
        from .user import CourseEnrollment
        enrollments = CourseEnrollment.query.filter_by(
            course_id=self.id,
            status='pending'
        ).all()
        return [e.student for e in enrollments]
    
    def __repr__(self):
        return f'<Course {self.name}>'