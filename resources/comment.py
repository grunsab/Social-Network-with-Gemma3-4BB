from flask import request, current_app
from flask_restful import Resource, reqparse, fields, marshal_with
from flask_login import current_user, login_required

from models import db, Post, Comment, User, PostPrivacy # Import necessary models

# --- Field definitions for Marshaling --- 
# Re-use author_fields if defined elsewhere or define here
author_fields = {
    'id': fields.Integer,
    'username': fields.String
}

comment_fields = {
    'id': fields.Integer,
    'content': fields.String,
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'author': fields.Nested(author_fields), # Nested author data
    'post_id': fields.Integer
}

# Parser for creating a comment
comment_parser = reqparse.RequestParser()
comment_parser.add_argument('content', type=str, required=True, help='Comment content cannot be empty', location='json')

class CommentListResource(Resource):
    # Get comments for a specific post
    @login_required
    @marshal_with(comment_fields) # Use marshal_with for list items
    def get(self, post_id):
        post = Post.query.get_or_404(post_id)
        # TODO: Add permission check - can the current user view this post?
        # (Similar logic as in PostResource.get)
        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.timestamp.asc()).all()
        return comments # Marshal list of comments

    # Create a new comment for a specific post
    @login_required
    @marshal_with(comment_fields)
    def post(self, post_id):
        post = Post.query.get_or_404(post_id)
        # TODO: Add permission check - can the current user comment on this post?
        
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