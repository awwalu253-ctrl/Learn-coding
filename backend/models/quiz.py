# backend/models/quiz.py
from datetime import datetime
from ..extensions import db

class QuizGroup(db.Model):
    __tablename__ = 'quiz_group'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    time_limit = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    author = db.relationship('User', backref='created_quizzes')
    questions = db.relationship('QuizQuestion', backref='quiz_group', lazy=True, cascade='all, delete-orphan')
    answers = db.relationship('QuizAnswer', backref='quiz_group', lazy=True)
    
    def get_student_score(self, student_id):
        answers = QuizAnswer.query.filter_by(
            quiz_group_id=self.id, student_id=student_id
        ).all()
        if not answers:
            return None
        correct = sum(1 for a in answers if a.is_correct)
        return {
            'correct': correct,
            'total': len(answers),
            'score': int((correct / len(answers)) * 100) if answers else 0
        }

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_question'
    
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    quiz_group_id = db.Column(db.Integer, db.ForeignKey('quiz_group.id'), nullable=False)

class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answer'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_group_id = db.Column(db.Integer, db.ForeignKey('quiz_group.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_question.id'), nullable=False)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    question = db.relationship('QuizQuestion', backref='answers')