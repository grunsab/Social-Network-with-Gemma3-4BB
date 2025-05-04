# from app import db, UserMixin # Removed import from app
from flask_login import UserMixin # Kept UserMixin import
from extensions import db # Added import from extensions
from datetime import datetime, timezone
import uuid # Add uuid for code generation

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy=True)
    interests = db.relationship('UserInterest', backref='user', lazy=True)
    invites_left = db.Column(db.Integer, default=3, nullable=False) # Max 3 invites per user initially
    issued_codes = db.relationship('InviteCode', backref='issuer', lazy=True, foreign_keys='InviteCode.issuer_id')
    used_invite_code = db.Column(db.String(36), nullable=True) # Store the code used for registration

    def __repr__(self):
        return f'<User {self.username}>'

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_url = db.Column(db.String(512), nullable=True) # URL for the image stored in S3
    image_classification = db.Column(db.JSON, nullable=True) # Store classification results as JSON
    score = db.Column(db.Float, nullable=True, default=0.0, index=True) # Added combined score field

    def __repr__(self):
        return f'<Post {self.content[:50]}...>'

class UserInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    score = db.Column(db.Float, default=0.0)

    # Ensure a user has only one interest record per category
    __table_args__ = (db.UniqueConstraint('user_id', 'category', name='uq_user_category'),)

    def __repr__(self):
        return f'<UserInterest User: {self.user_id} Category: {self.category} Score: {self.score}>'

# New InviteCode model
class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    issuer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # User who registered with this code
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Define the relationship for the user who used the code
    used_by = db.relationship('User', foreign_keys=[used_by_id])

    def __repr__(self):
        return f'<InviteCode {self.code} - Issued by {self.issuer_id} - Used: {self.is_used}>' 