# from app import db, UserMixin # Removed import from app
from flask_login import UserMixin # Kept UserMixin import
from extensions import db # Added import from extensions
from datetime import datetime, timezone
import uuid # Add uuid for code generation
import enum # Import enum for FriendRequestStatus and PostPrivacy

# Enum for Friend Request Status
class FriendRequestStatus(enum.Enum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'

# Enum for Post Privacy
class PostPrivacy(enum.Enum):
    PUBLIC = 'public'  # Viewable by everyone
    FRIENDS = 'friends'  # Viewable only by friends

# New FriendRequest model
class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.Enum(FriendRequestStatus), default=FriendRequestStatus.PENDING, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships to get User objects from IDs
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_requests')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_requests')

    # Ensure a unique pending request between two users
    __table_args__ = (db.UniqueConstraint('sender_id', 'receiver_id', name='uq_friend_request'),)

    def __repr__(self):
        return f'<FriendRequest {self.sender.username} -> {self.receiver.username}: {self.status.value}>'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    interests = db.relationship('UserInterest', backref='user', lazy=True)
    invites_left = db.Column(db.Integer, default=3, nullable=False) # Max 3 invites per user initially
    issued_codes = db.relationship('InviteCode', backref='issuer', lazy=True, foreign_keys='InviteCode.issuer_id')
    used_invite_code = db.Column(db.String(36), nullable=True) # Store the code used for registration

    def __repr__(self):
        return f'<User {self.username}>'

    # --- Friendship Methods ---

    def get_friends(self):
        """Returns a list of users who are friends (accepted requests)."""
        # Find accepted requests where the user is the sender
        sent_accepted = FriendRequest.query.filter_by(sender_id=self.id, status=FriendRequestStatus.ACCEPTED).all()
        friend_ids_sent = [req.receiver_id for req in sent_accepted]

        # Find accepted requests where the user is the receiver
        received_accepted = FriendRequest.query.filter_by(receiver_id=self.id, status=FriendRequestStatus.ACCEPTED).all()
        friend_ids_received = [req.sender_id for req in received_accepted]

        # Combine IDs and get unique User objects
        all_friend_ids = set(friend_ids_sent + friend_ids_received)
        return User.query.filter(User.id.in_(all_friend_ids)).all()

    def is_friend(self, user):
        """Checks if this user is friends with another user (accepted request exists)."""
        return FriendRequest.query.filter(
            ((FriendRequest.sender_id == self.id) & (FriendRequest.receiver_id == user.id) |
             (FriendRequest.sender_id == user.id) & (FriendRequest.receiver_id == self.id)),
            FriendRequest.status == FriendRequestStatus.ACCEPTED
        ).count() > 0

    def unfriend(self, user):
        """Removes friendship (deletes the accepted FriendRequest)."""
        request = FriendRequest.query.filter(
            ((FriendRequest.sender_id == self.id) & (FriendRequest.receiver_id == user.id) |
             (FriendRequest.sender_id == user.id) & (FriendRequest.receiver_id == self.id)),
            FriendRequest.status == FriendRequestStatus.ACCEPTED
        ).first()
        if request:
            db.session.delete(request)
            return True
        return False

    # --- Friend Request Methods ---

    def send_friend_request(self, user):
        """Sends a friend request to another user."""
        if self == user or self.is_friend(user) or self.has_pending_request_to(user) or self.has_pending_request_from(user):
            return None # Cannot send request to self, existing friend, or if pending request exists either way
        request = FriendRequest(sender_id=self.id, receiver_id=user.id, status=FriendRequestStatus.PENDING)
        db.session.add(request)
        return request

    def accept_friend_request(self, request_id):
        """Accepts a friend request received by this user."""
        request = FriendRequest.query.filter_by(id=request_id, receiver_id=self.id, status=FriendRequestStatus.PENDING).first()
        if request:
            request.status = FriendRequestStatus.ACCEPTED
            # Optional: Delete any reverse pending request if it exists (user B sent request to user A after A sent to B)
            reverse_request = FriendRequest.query.filter_by(
                sender_id=request.receiver_id,
                receiver_id=request.sender_id,
                status=FriendRequestStatus.PENDING
            ).first()
            if reverse_request:
                db.session.delete(reverse_request)
            return True
        return False

    def reject_friend_request(self, request_id):
        """Rejects a friend request received by this user."""
        request = FriendRequest.query.filter_by(id=request_id, receiver_id=self.id, status=FriendRequestStatus.PENDING).first()
        if request:
            # Option 1: Set status to REJECTED (keeps history)
            # request.status = FriendRequestStatus.REJECTED
            # Option 2: Delete the request (simpler, less history)
            db.session.delete(request)
            return True
        return False

    def cancel_friend_request(self, user):
        """Cancels a friend request sent by this user to another user."""
        request = FriendRequest.query.filter_by(sender_id=self.id, receiver_id=user.id, status=FriendRequestStatus.PENDING).first()
        if request:
            db.session.delete(request)
            return True
        return False

    def has_pending_request_to(self, user):
        """Checks if this user has sent a pending request to another user."""
        return FriendRequest.query.filter_by(sender_id=self.id, receiver_id=user.id, status=FriendRequestStatus.PENDING).count() > 0

    def has_pending_request_from(self, user):
        """Checks if this user has received a pending request from another user."""
        return FriendRequest.query.filter_by(sender_id=user.id, receiver_id=self.id, status=FriendRequestStatus.PENDING).count() > 0

    def get_pending_received_requests(self):
        """Returns a list of pending friend requests received by this user."""
        return FriendRequest.query.filter_by(receiver_id=self.id, status=FriendRequestStatus.PENDING).order_by(FriendRequest.timestamp.desc()).all()

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_url = db.Column(db.String(512), nullable=True) # URL for the image stored in S3
    classification_scores = db.Column(db.JSON, nullable=True) # Store combined classification results as JSON
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    privacy = db.Column(db.Enum(PostPrivacy), default=PostPrivacy.PUBLIC, nullable=False)  # Default to public

    def __repr__(self):
        return f'<Post {self.content[:50]}...>'

    def is_visible_to(self, user):
        """Check if a post is visible to a given user based on privacy settings"""
        # Post author can always see their own posts
        if self.user_id == user.id:
            return True
            
        # If public, anyone can see
        if self.privacy == PostPrivacy.PUBLIC:
            return True
            
        # If friends-only, check friendship
        if self.privacy == PostPrivacy.FRIENDS:
            author = User.query.get(self.user_id)
            return author.is_friend(user)
            
        # Default fallback - shouldn't reach here with proper enum constraints
        return False

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    def __repr__(self):
        return f'<Comment {self.content[:30]}...>'

class PostCategoryScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<PostCategoryScore {self.id} - Post: {self.post_id} - Category: {self.category} - Score: {self.score}>'

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