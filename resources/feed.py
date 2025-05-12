from flask import current_app, jsonify
from flask_restful import Resource, fields, marshal_with, reqparse, abort
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import desc, func, union_all, or_, and_, case # Added case
import math # For ceiling division in pagination calculation
import sys # Added for print statements

from models import db, User, Post, UserInterest, PostCategoryScore, PostPrivacy, FriendRequest, FriendRequestStatus
from resources.post import FormattedContent  # Import formatted content field for ampersounds

# --- Field definitions for Marshaling ---
# Attempt to re-use or define fields consistently
author_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'profile_picture': fields.String
}

post_feed_fields = {
    'id': fields.Integer,
    'content': FormattedContent(attribute=lambda x: x),  # Use formatted content with ampersound spans
    'image_url': fields.String,
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'privacy': fields.String(attribute='privacy.name'), 
    'author': fields.Nested(author_fields),
    'classification_scores': fields.Raw(attribute='classification_scores'), 
    'comments_count': fields.Integer,  # Added comment count to feed fields
    'likes_count': fields.Integer, # Added likes count to feed fields
    # Add relevance score if we decide to calculate and return it
    # 'relevance_score': fields.Float 
}

feed_response_fields = {
    'posts': fields.List(fields.Nested(post_feed_fields)),
    'page': fields.Integer,
    'per_page': fields.Integer,
    'total_items': fields.Integer, # Total matching items across all pages
    'total_pages': fields.Integer,
    'message': fields.String(default=None)
}

# --- Parser ---
feed_parser = reqparse.RequestParser()
feed_parser.add_argument('page', type=int, default=1, location='args')
feed_parser.add_argument('per_page', type=int, default=10, location='args')
feed_parser.add_argument('sort_by', type=str, default='relevance', location='args', choices=('relevance', 'recency'), help='Sort order for the feed. "relevance" (default) or "recency".')

class FeedResource(Resource):
    @login_required
    @marshal_with(feed_response_fields)
    def get(self):
        args = feed_parser.parse_args()
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        offset = (page - 1) * per_page
        
        blocked_categories = current_app.config.get('BLOCKED_CATEGORIES', set())
        friend_ids = current_user.get_friend_ids()
        posts_unfiltered = [] 
        message = None
        total_items = 0

        # --- Get top user interests --- 
        user_interests = UserInterest.query.filter_by(user_id=current_user.id).order_by(UserInterest.score.desc()).limit(5).all()
        interested_categories = [interest.category for interest in user_interests]

        # Common visibility filter for posts
        # Exclude own posts from the feed
        # not_own_post_filter = Post.user_id != current_user.id
        visibility_filter = or_(
            Post.privacy == PostPrivacy.PUBLIC,
            and_(
                Post.privacy == PostPrivacy.FRIENDS,
                Post.user_id.in_(friend_ids)
            )
        )
        combined_filter = and_(
            #not_own_post_filter,
            visibility_filter
        )

        # Get total items for pagination (applies to both sort methods)
        total_items = db.session.query(func.count(Post.id)).filter(combined_filter).scalar() or 0

        if sort_by == 'relevance':
            # --- Relevance Sorting Logic --- 
            # Determine weight subquery (user or global interests)
            if interested_categories:
                weight_query = db.session.query(
                    UserInterest.category,
                    UserInterest.score.label('weight')
                ).filter(
                    UserInterest.user_id == current_user.id,
                    UserInterest.category.in_(interested_categories)
                )
            else:
                weight_query = db.session.query(
                    UserInterest.category,
                    func.sum(UserInterest.score).label('weight')
                ).group_by(UserInterest.category)
            weight_subq = weight_query.subquery('weight_subq')

            # Define feed score weights
            R_WEIGHT = current_app.config.get('FEED_RELEVANCE_WEIGHT', 0.2)
            P_WEIGHT = current_app.config.get('FEED_POPULARITY_WEIGHT', 0.05)
            D_WEIGHT = current_app.config.get('FEED_RECENCY_WEIGHT', 0.7)
            E_WEIGHT = current_app.config.get('FEED_ENGAGEMENT_WEIGHT', 0.05)
            S_PENALTY_WEIGHT = current_app.config.get('FEED_SELF_POST_PENALTY_WEIGHT', 0.2)

            # Define normalization constants
            K_RELEVANCE = current_app.config.get('FEED_K_RELEVANCE', 10.0)
            K_COMMENTS = current_app.config.get('FEED_K_COMMENTS', 10.0)
            K_LIKES = current_app.config.get('FEED_K_LIKES', 20.0)

            # Build feed scoring query
            feed_query = db.session.query(
                Post.id.label('post_id'),
                (
                    R_WEIGHT * (
                        func.coalesce(func.sum(PostCategoryScore.score * weight_subq.c.weight), 0) /
                        (func.coalesce(func.sum(PostCategoryScore.score * weight_subq.c.weight), 0) + K_RELEVANCE)
                    )
                    + P_WEIGHT * (
                        func.coalesce(Post.comments_count, 0) /
                        (func.coalesce(Post.comments_count, 0) + K_COMMENTS)
                    ) 
                    + D_WEIGHT * (1.0 / (1.0 + (func.extract('epoch', func.now() - Post.timestamp) / 3600.0))) 
                    + E_WEIGHT * (
                        func.coalesce(Post.likes_count, 0) /
                        (func.coalesce(Post.likes_count, 0) + K_LIKES)
                    ) 
                    - case((Post.user_id == current_user.id, S_PENALTY_WEIGHT), else_=0) 
                ).label('feed_score'),
                Post.timestamp.label('timestamp')
            ).select_from(Post).outerjoin(
                PostCategoryScore, Post.id == PostCategoryScore.post_id
            ).outerjoin(
                weight_subq, PostCategoryScore.category == weight_subq.c.category
            ).filter(
                combined_filter
            ).group_by(
                Post.id, Post.timestamp
            )
            ordered_feed = feed_query.order_by(desc('feed_score'), desc('timestamp'))
            message = (
                "Showing personalized feed based on your interests."
                if interested_categories else
                "Showing popular posts based on global interests."
            )
        elif sort_by == 'recency':
            # --- Recency Sorting Logic --- 
            feed_query = db.session.query(
                Post.id.label('post_id'),
                Post.timestamp.label('timestamp') # Only need timestamp for ordering by recency
            ).select_from(Post).filter(
                combined_filter
            )
            ordered_feed = feed_query.order_by(desc('timestamp'))
            message = "Showing feed sorted by most recent posts."
        else:
            # This case should ideally not be reached due to 'choices' in argparser
            abort(400, message="Invalid sort_by parameter.")

        # Paginate the ordered feed
        page_items = ordered_feed.limit(per_page).offset(offset).all()
        ordered_ids = [item.post_id for item in page_items]

        # Fetch posts with eager loading, preserving the order from the feed query
        posts_unfiltered = []
        if ordered_ids:
            # Create a mapping of ID to its order index
            order_map = {pid: index for index, pid in enumerate(ordered_ids)}
            posts_query = Post.query.filter(Post.id.in_(ordered_ids)).options(
                joinedload(Post.author),
                joinedload(Post.category_scores),
                undefer(Post.comments_count) # Ensure comments_count is loaded
                # undefer(Post.likes_count) # Ensure likes_count is loaded - already handled by column_property
            )
            
            # Sort the fetched posts based on the order_map
            # This is crucial because the IN clause doesn't guarantee order
            all_posts_for_page = posts_query.all()
            posts_map = {p.id: p for p in all_posts_for_page}
            # Reconstruct in the correct order
            posts_unfiltered = [posts_map[pid] for pid in ordered_ids if pid in posts_map]

        # --- Final Step: Filter results by blocked categories ---
        # This step is applied after pagination and fetching full post objects
        filtered_posts = []
        for post in posts_unfiltered:
            post_categories = {score.category for score in post.category_scores}
            if not post_categories.intersection(blocked_categories):
                filtered_posts.append(post)

        # Calculate total pages based on total_items (which was counted *before* category filtering)
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

        return {
            'posts': filtered_posts, 
            'page': page,
            'per_page': per_page,
            'total_items': total_items, 
            'total_pages': total_pages,
            'message': message
        }