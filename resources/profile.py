from flask import current_app
from flask_restful import Resource, fields, marshal_with, abort
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from models import db, User, Post, UserInterest, PostPrivacy, FriendRequest, FriendRequestStatus # Added FriendRequest

# --- Field Definitions for Marshaling ---
# Re-use author_fields if defined elsewhere or define similar user fields
user_profile_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'email': fields.String, # Maybe only show to self or friends?
    'profile_picture': fields.String,
    'invites_left': fields.Integer, # Maybe only show to self?
    # Add join date, etc. if needed
}

# Re-use or define author fields consistently
author_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'profile_picture': fields.String
}

# <<< Use more complete post fields for profile view >>>
post_fields_for_profile = {
    'id': fields.Integer,
    'content': fields.String,
    'image_url': fields.String,
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'privacy': fields.String(attribute='privacy.name'), 
    'author': fields.Nested(author_fields), # Include author for Post component
    'classification_scores': fields.Raw(attribute='classification_scores'), 
}

interest_fields = {
    'category': fields.String,
    'score': fields.Float
}

profile_data_fields = {
    'user': fields.Nested(user_profile_fields),
    'posts': fields.List(fields.Nested(post_fields_for_profile)), # <<< Use updated post fields
    'interests': fields.List(fields.Nested(interest_fields)),
    'friendship_status': fields.String, 
    'pending_request_id': fields.Integer(default=None) # <<< Add field for request ID
}

class ProfileResource(Resource):
    @login_required
    @marshal_with(profile_data_fields)
    def get(self, username):
        user = User.query.filter_by(username=username).first()
        if not user:
            abort(404, message=f"User '{username}' not found.")

        status = 'NONE'
        pending_request_id = None # Initialize request ID
        request_obj = None # Store the request object if found

        if user.id == current_user.id:
            status = 'SELF'
        else:
            # Check for existing request first (covers PENDING_SENT and PENDING_RECEIVED)
            request_obj = FriendRequest.query.filter(
                ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == user.id)) |
                ((FriendRequest.sender_id == user.id) & (FriendRequest.receiver_id == current_user.id))
            ).first()

            if request_obj:
                 pending_request_id = request_obj.id
                 if request_obj.status == FriendRequestStatus.ACCEPTED:
                     status = 'FRIENDS'
                 elif request_obj.sender_id == current_user.id:
                     status = 'PENDING_SENT'
                 else: # request_obj.receiver_id == current_user.id
                     status = 'PENDING_RECEIVED'
            # If no request exists, status remains 'NONE'
                 
        # Determine which posts to show based on status
        posts_query = Post.query.filter_by(user_id=user.id)
        if status == 'SELF' or status == 'FRIENDS':
            # Show all posts (Public, Friends Only, Private - if we add Private)
            pass # No additional privacy filter needed for self/friends
        else:
            # Show only Public posts
            posts_query = posts_query.filter(Post.privacy == PostPrivacy.PUBLIC)
        
        # <<< Ensure author is loaded along with scores >>>
        posts = posts_query.options(
            joinedload(Post.author), 
            joinedload(Post.category_scores)
        ).order_by(Post.timestamp.desc()).all()
        
        # Filter posts by blocked categories (similar to PostListResource)
        blocked_categories = current_app.config.get('BLOCKED_CATEGORIES', set())
        filtered_posts = []
        for p in posts:
             post_categories = {score.category for score in p.category_scores}
             if not post_categories.intersection(blocked_categories):
                 filtered_posts.append(p)

        # Fetch interests
        interests = UserInterest.query.filter_by(user_id=user.id).order_by(UserInterest.score.desc()).all()
        
        # Adjust user data visibility based on status (optional)
        # e.g., don't show email or invites_left to non-self
        profile_user_data = user
        if status != 'SELF':
             # Example: mask sensitive fields if needed
             # profile_user_data.email = None 
             # profile_user_data.invites_left = None 
             pass # For now, return full user object, marshaling handles selection

        return {
            'user': profile_user_data,
            'posts': filtered_posts,
            'interests': interests,
            'friendship_status': status,
            'pending_request_id': pending_request_id if status in ['PENDING_SENT', 'PENDING_RECEIVED'] else None # Return ID only if relevant
        } 