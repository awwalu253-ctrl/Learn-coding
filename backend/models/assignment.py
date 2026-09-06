# backend/models/assignment.py
from datetime import datetime
from ..extensions import db

class Assignment(db.Model):
    __tablename__ = 'assignment'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    max_score = db.Column(db.Float, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    file_path = db.Column(db.String(200), nullable=True)
    file_name = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.String(20), nullable=True)
    
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    author = db.relationship('User', backref='created_assignments')
    submissions = db.relationship('AssignmentSubmission', backref='assignment', lazy=True, cascade='all, delete-orphan')
    
    def is_past_due(self):
        return datetime.utcnow() > self.due_date
    
    def get_submission_for_student(self, student_id):
        return AssignmentSubmission.query.filter_by(
            assignment_id=self.id, student_id=student_id
        ).first()

class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submission'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    content = db.Column(db.Text)
    file_path = db.Column(db.String(200))
    file_name = db.Column(db.String(100))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_graded = db.Column(db.Boolean, default=False)
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)