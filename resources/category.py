from flask import current_app
from flask_restful import Resource, fields, marshal_with, reqparse, abort
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from sqlalchemy import desc # For ordering
import json
import os
import math

from models import db, User, Post, PostCategoryScore, PostPrivacy, FriendRequest, FriendRequestStatus

# --- Field definitions (Reuse from other resources or define here) ---
author_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'profile_picture': fields.String
}

post_category_fields = {
    'id': fields.Integer,
    'content': fields.String,
    'image_url': fields.String,
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'privacy': fields.String(attribute='privacy.name'), 
    'author': fields.Nested(author_fields),
    'classification_scores': fields.Raw(attribute='classification_scores') 
}

category_response_fields = {
    'category_name': fields.String,
    'posts': fields.List(fields.Nested(post_category_fields)),
    'page': fields.Integer,
    'per_page': fields.Integer,
    'total_items': fields.Integer,
    'total_pages': fields.Integer
}

# --- Parser ---
category_parser = reqparse.RequestParser()
category_parser.add_argument('page', type=int, default=1, location='args')
category_parser.add_argument('per_page', type=int, default=10, location='args')

class CategoryResource(Resource):
    @login_required
    @marshal_with(category_response_fields)
    def get(self, category_name):
        args = category_parser.parse_args()
        page = args['page']
        per_page = args['per_page']
        offset = (page - 1) * per_page

        blocked_categories = current_app.config.get('BLOCKED_CATEGORIES', set())
        gemma_classifier = current_app.config.get('GEMMA_CLASSIFICATION') # Need for all_categories fallback

        # --- Validate Category --- 
        # Load valid categories
        all_categories = []
        categories_path = os.path.join(current_app.root_path, 'categories.json')
        try:
            with open(categories_path, 'r') as f:
                all_categories = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
             if gemma_classifier:
                 all_categories = gemma_classifier.categories # Fallback to classifier default
             else: # Absolute fallback
                 all_categories = ["Technology", "Travel", "Food", "Art"] 

        if category_name not in all_categories or category_name in blocked_categories:
            abort(404, message=f"Category '{category_name}' not found or is blocked.")

        # --- Query Posts for Category --- 
        # Find posts with the specified category having a score >= 0.5 (or adjust threshold)
        relevant_post_scores_subq = db.session.query(PostCategoryScore.post_id).filter(
            PostCategoryScore.category == category_name,
            PostCategoryScore.score >= 0.5 
        ).subquery()

        # Base query for posts in this category
        base_query = Post.query.join(
            relevant_post_scores_subq, Post.id == relevant_post_scores_subq.c.post_id
        ).options(joinedload(Post.author)) # Eager load author
        
        # Apply visibility filters (Public, Friends-Only from Friends, Own)
        friend_ids = current_user.get_friend_ids()
        visibility_filter = (
            (Post.privacy == PostPrivacy.PUBLIC) |
            (Post.user_id == current_user.id) |
            (
                (Post.privacy == PostPrivacy.FRIENDS) &
                Post.user_id.in_(friend_ids)
            )
        )
        
        filtered_query = base_query.filter(visibility_filter)

        # Get total count for pagination
        total_items = filtered_query.count()
        
        # Apply ordering and pagination
        paginated_posts = filtered_query.order_by(Post.timestamp.desc()).limit(per_page).offset(offset).all()

        # Note: Category blocking already handled by checking category_name itself
        
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

        return {
            'category_name': category_name,
            'posts': paginated_posts,
            'page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages
        } 