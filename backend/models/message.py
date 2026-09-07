# backend/models/message.py
from datetime import datetime
from ..extensions import db

class Message(db.Model):
    __tablename__ = 'message'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    parent_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')
    replies = db.relationship('Message', backref='parent', remote_side=[id])
    
    __table_args__ = (
        db.Index('idx_message_sender', 'sender_id'),
        db.Index('idx_message_receiver', 'receiver_id'),
        db.Index('idx_message_created', 'created_at'),
        db.Index('idx_message_is_read', 'is_read'),
    )
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    def get_replies(self):
        return Message.query.filter_by(parent_message_id=self.id).order_by(Message.created_at.asc()).all()
    
    def __repr__(self):
        return f'<Message {self.id} - {self.sender.username} -> {self.receiver.username}>'