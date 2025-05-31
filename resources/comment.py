from flask import request, current_app
from flask_restful import Resource, reqparse, fields, marshal_with
from flask_login import current_user, login_required

from models import db, Post, Comment, User, PostPrivacy, Notification # Import Notification
# Import the formatter function
from utils import format_text_with_ampersounds 

# --- Field definitions for Marshaling --- 
# Re-use author_fields if defined elsewhere or define here
author_fields = {
    'id': fields.Integer,
    'username': fields.String
}

# Formatted content field for Ampersounds in comments
class FormattedCommentContent(fields.Raw):
    def format(self, value):
        # 'value' here is the comment object itself, passed via attribute
        comment_object = value
        # Ensure author is loaded. If not, this will cause a lazy load.
        # It's better if author is eager-loaded in the query.
        if not comment_object.content or not comment_object.author:
            return comment_object.content
        return format_text_with_ampersounds(comment_object.content, comment_object.author.username)

comment_fields = {
    'id': fields.Integer,
    'content': FormattedCommentContent(attribute=lambda x: x), # Pass the whole comment object
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'author': fields.Nested(author_fields), # Nested author data
    'post_id': fields.Integer
}

# Parser for creating a comment
comment_parser = reqparse.RequestParser()
comment_parser.add_argument('content', type=str, required=True, help='Comment content cannot be empty', location='json')

class CommentListResource(Resource):
    # Get comments for a specific post
    # @login_required # Removed for public comment viewing
    @marshal_with(comment_fields) # Use marshal_with for list items
    def get(self, post_id):
        post = Post.query.get_or_404(post_id)
        
        # --- BEGIN PERMISSION CHECK ---
        can_view_post = False
        is_post_public = post.privacy == PostPrivacy.PUBLIC

        if is_post_public:
            can_view_post = True
        elif current_user.is_authenticated: # Checks for logged-in users for non-public posts
            is_author_of_post = post.user_id == current_user.id
            if is_author_of_post:
                can_view_post = True
            elif post.privacy == PostPrivacy.FRIENDS:
                # Assuming current_user has an is_friend method that takes the post's author object or ID
                if hasattr(current_user, 'is_friend') and post.author:
                     can_view_post = current_user.is_friend(post.author)
                # else: Handle case where is_friend method or post.author is not available, though unlikely with proper setup
        
        if not can_view_post:
            # Differentiate message for logged-in vs anonymous if post is not public
            if not is_post_public and current_user.is_authenticated:
                 return {'message': 'You do not have permission to view comments for this post.'}, 403
            elif not is_post_public: # Anonymous user trying to access non-public post comments
                 return {'message': 'Comments for this post are not publicly viewable.'}, 401 # Or 403
            # If it's public, this path shouldn't be hit due to logic above.
            # However, as a fallback, if somehow can_view_post is false for a public post, deny.
            # This case should ideally not occur with the current logic.
            return {'message': 'Cannot view comments.'}, 403
        # --- END PERMISSION CHECK ---

        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.timestamp.asc()).all()
        return comments # Marshal list of comments

    # Create a new comment for a specific post
    @login_required
    @marshal_with(comment_fields)
    def post(self, post_id):
        post = Post.query.get_or_404(post_id)

        # --- BEGIN PERMISSION CHECK ---
        is_author_of_post = post.user_id == current_user.id
        is_post_public = post.privacy == PostPrivacy.PUBLIC
        can_comment_on_post = False

        if is_post_public or is_author_of_post:
            can_comment_on_post = True
        elif post.privacy == PostPrivacy.FRIENDS:
            if hasattr(current_user, 'is_friend') and post.author:
                can_comment_on_post = current_user.is_friend(post.author)
        
        if not can_comment_on_post:
            return {'message': 'You do not have permission to comment on this post.'}, 403
        # --- END PERMISSION CHECK ---

        args = comment_parser.parse_args()
        content = args['content']

        new_comment = Comment(
            content=content,
            user_id=current_user.id,
            post_id=post_id
        )
        try:
            db.session.add(new_comment)
            db.session.commit()
            # Create notifications: notify post author and previous commenters
            try:
                # Notify post author if commenter is not the author
                if post.user_id != current_user.id:
                    notif = Notification(user_id=post.user_id, actor_id=current_user.id, post_id=post_id, comment_id=new_comment.id)
                    db.session.add(notif)
                # Notify other previous commenters
                prev_user_ids = {c.user_id for c in Comment.query.filter_by(post_id=post_id).all()}
                prev_user_ids.discard(current_user.id)
                prev_user_ids.discard(post.user_id)
                for uid in prev_user_ids:
                    notif = Notification(user_id=uid, actor_id=current_user.id, post_id=post_id, comment_id=new_comment.id)
                    db.session.add(notif)
                db.session.commit()
            except Exception:
                db.session.rollback()
            return new_comment, 201 # Return created comment with 201 status
        except Exception as e:
            db.session.rollback()
            print(f"Error creating comment: {e}")
            return {'message': 'Failed to create comment'}, 500

class CommentResource(Resource):
    # Delete a specific comment
    @login_required
    def delete(self, comment_id):
        comment = Comment.query.get_or_404(comment_id)

        # Check if the current user is the author of the comment
        if comment.user_id != current_user.id:
            return {'message': 'You do not have permission to delete this comment'}, 403

        try:
            db.session.delete(comment)
            db.session.commit()
            return {'message': 'Comment deleted successfully'}, 200 # Or 204 No Content
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting comment: {e}")
            return {'message': 'Failed to delete comment'}, 500