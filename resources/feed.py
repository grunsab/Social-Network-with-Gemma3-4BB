from flask import current_app, jsonify
from flask_restful import Resource, fields, marshal_with, reqparse, abort
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import desc, func, union_all, or_, and_ # Added or_ and and_
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


class FeedResource(Resource):
    @login_required
    @marshal_with(feed_response_fields)
    def get(self):
        args = feed_parser.parse_args()
        page = args['page']
        per_page = args['per_page']
        offset = (page - 1) * per_page
        
        blocked_categories = current_app.config.get('BLOCKED_CATEGORIES', set())
        friend_ids = current_user.get_friend_ids()
        posts_unfiltered = [] # Initialize list for posts before category filtering
        message = None
        total_items = 0

        # --- Get top user interests --- 
        user_interests = UserInterest.query.filter_by(user_id=current_user.id).order_by(UserInterest.score.desc()).limit(5).all()
        interested_categories = [interest.category for interest in user_interests]

        if not interested_categories:
            # --- Fallback: Recent Posts (If no interests) ---
            message = "Showing recent posts. Explore more to personalize your feed!"
            print(f"DEBUG: User {current_user.id} - Taking FEED FALLBACK path", file=sys.stderr)
            combined_filter = or_(
                Post.user_id == current_user.id,
                Post.privacy == PostPrivacy.PUBLIC,
                and_(
                    Post.privacy == PostPrivacy.FRIENDS,
                    Post.user_id.in_(friend_ids)
                )
            )
            # Count total items matching the filter (before category blocking)
            total_items = db.session.query(func.count(Post.id)).filter(combined_filter).scalar()
            print(f"DEBUG: User {current_user.id} - Fallback total_items: {total_items}", file=sys.stderr)

            # Fetch posts for the current page
            posts_unfiltered = Post.query.options(
                joinedload(Post.author),
                joinedload(Post.category_scores), # Need scores for category blocking below
                undefer(Post.comments_count)  # Ensure comments_count is loaded
            ).filter(combined_filter).order_by(Post.timestamp.desc()).limit(per_page).offset(offset).all()
            print(f"DEBUG: User {current_user.id} - Fallback posts_unfiltered IDs: {[p.id for p in posts_unfiltered]}", file=sys.stderr)

        else:
            # --- Personalized Feed Logic --- 
            message = "Showing personalized feed based on your interests."
            print(f"DEBUG: User {current_user.id} - Taking FEED PERSONALIZED path with interests: {interested_categories}", file=sys.stderr)
            user_interest_subq = db.session.query(
                UserInterest.category,
                UserInterest.score
            ).filter(
                UserInterest.user_id == current_user.id,
                UserInterest.category.in_(interested_categories)
            ).subquery('user_interest_subq')

            # Base query for calculating relevance of posts (Public or Friend's) not authored by current user
            relevance_base_query = db.session.query(
                Post.id.label('post_id'),
                func.coalesce(func.sum(
                    PostCategoryScore.score * user_interest_subq.c.score
                ), 0).label('relevance_score'),
                Post.timestamp.label('timestamp')
            ).select_from(Post).outerjoin(
                PostCategoryScore, Post.id == PostCategoryScore.post_id
            ).outerjoin(
                user_interest_subq, PostCategoryScore.category == user_interest_subq.c.category
            ).filter(
                or_(
                    Post.user_id == current_user.id,
                    Post.privacy == PostPrivacy.PUBLIC,
                    and_(
                        Post.privacy == PostPrivacy.FRIENDS,
                        Post.user_id.in_(friend_ids)
                    )
                )
            ).group_by(Post.id, Post.timestamp)

            # Order by relevance score, then timestamp
            ordered_relevance_query = relevance_base_query.order_by(
                desc('relevance_score'), # Posts with no matching score/interest will have score 0
                desc('timestamp')
            )

            # Get total count for pagination
            # Let's recalculate total_items based on visibility filter only for pagination accuracy.
            visibility_filter_for_count = or_(
                Post.user_id == current_user.id,
                Post.privacy == PostPrivacy.PUBLIC,
                and_(
                    Post.privacy == PostPrivacy.FRIENDS,
                    Post.user_id.in_(friend_ids)
                )
            )
            total_items = db.session.query(func.count(Post.id)).filter(visibility_filter_for_count).scalar()
            # total_items = ordered_relevance_query.count() # Old count might be inaccurate with outer join
            print(f"DEBUG: User {current_user.id} - Personalized total_items (recalculated): {total_items}", file=sys.stderr)

            # Apply pagination to the relevance query to get IDs for the current page
            paginated_relevance_items = ordered_relevance_query.limit(per_page).offset(offset).all()
            ordered_post_ids = [item.post_id for item in paginated_relevance_items]
            print(f"DEBUG: User {current_user.id} - Personalized ordered_post_ids: {ordered_post_ids}", file=sys.stderr)

            # Fetch full Post objects for these IDs
            if ordered_post_ids:
                posts_unfiltered = Post.query.filter(Post.id.in_(ordered_post_ids)).options(
                    joinedload(Post.author),
                    joinedload(Post.category_scores),
                    undefer(Post.content),
                    undefer(Post.comments_count)  # Load comments_count for personalized posts
                ).all()
                # Re-order based on the relevance query result order
                posts_map = {p.id: p for p in posts_unfiltered}
                posts_unfiltered = [posts_map[pid] for pid in ordered_post_ids if pid in posts_map]
            else:
                posts_unfiltered = []

            # Note: Simplified augmentation logic compared to original.
            # Just adding a message if the first page is sparse.
            if page == 1 and len(posts_unfiltered) < min(5, per_page):
                message += " (Not many personalized posts found yet, showing most relevant.)"

        # --- Final Step: Filter results by blocked categories ---
        filtered_posts = []
        for post in posts_unfiltered:
            post_categories = {score.category for score in post.category_scores}
            if not post_categories.intersection(blocked_categories):
                filtered_posts.append(post)

        # --- Reorder current user's own posts without comments to bottom ---
        reordered_posts = []
        own_posts_no_comments = []
        for post in filtered_posts:
            if post.user_id == current_user.id and post.comments_count == 0:
                own_posts_no_comments.append(post)
            else:
                reordered_posts.append(post)
        filtered_posts = reordered_posts + own_posts_no_comments

        # Calculate total pages based on total_items (which was counted *before* category filtering)
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

        # Return marshaled response
        return {
            'posts': filtered_posts, 
            'page': page,
            'per_page': per_page,
            'total_items': total_items, 
            'total_pages': total_pages,
            'message': message
        }