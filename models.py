# from app import db, UserMixin # Removed import from app
from flask_login import UserMixin # Kept UserMixin import
from extensions import db # Added import from extensions
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy=True)
    interests = db.relationship('UserInterest', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), index=True, nullable=True) # Storing the Gemma classification

    def __repr__(self):
        return f'<Post {self.content[:50]}...>'

class UserInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, default=1) # Simple score, incremented per post in category

    # Ensure a user has only one interest record per category
    __table_args__ = (db.UniqueConstraint('user_id', 'category', name='uq_user_category'),)

    def __repr__(self):
        return f'<UserInterest User: {self.user_id} Category: {self.category} Score: {self.score}>' 