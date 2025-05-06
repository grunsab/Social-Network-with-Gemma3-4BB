from flask import current_app, jsonify
from flask_restful import Resource, fields, marshal_with, reqparse, abort
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload, undefer
from sqlalchemy import desc, func, union_all, or_, and_ # Added or_ and and_
import math # For ceiling division in pagination calculation
import sys # Added for print statements

from models import db, User, Post, UserInterest, PostCategoryScore, PostPrivacy, FriendRequest, FriendRequestStatus

# --- Field definitions for Marshaling ---
# Attempt to re-use or define fields consistently
author_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'profile_picture': fields.String
}

post_feed_fields = {
    'id': fields.Integer,
    'content': fields.String,
    'image_url': fields.String,
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'privacy': fields.String(attribute='privacy.name'), 
    'author': fields.Nested(author_fields),
    'classification_scores': fields.Raw(attribute='classification_scores'), 
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
            # Original filter excluded own posts. New filter includes them.
            combined_filter = or_(
                Post.user_id == current_user.id, # Own posts (all their privacy levels visible to them)
                and_( # Other users' posts
                    Post.user_id != current_user.id,
                    or_(
                        Post.privacy == PostPrivacy.PUBLIC, # Public posts from others
                        and_(
                            Post.privacy == PostPrivacy.FRIENDS, # Friends-only posts from friends
                            Post.user_id.in_(friend_ids)
                        )
                    )
                )
            )
            # Count total items matching the filter (before category blocking)
            total_items = db.session.query(func.count(Post.id)).filter(combined_filter).scalar()
            print(f"DEBUG: User {current_user.id} - Fallback total_items: {total_items}", file=sys.stderr)

            # Fetch posts for the current page
            posts_unfiltered = Post.query.options(
                joinedload(Post.author),
                joinedload(Post.category_scores) # Need scores for category blocking below
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
                # Use coalesce to handle potential null score if outer joins produce no match
                func.coalesce(func.sum(
                    PostCategoryScore.score * user_interest_subq.c.score
                ), 0).label('relevance_score'),
                Post.timestamp.label('timestamp')
            ).select_from(Post).outerjoin( # Changed to outerjoin
                PostCategoryScore, Post.id == PostCategoryScore.post_id
            ).outerjoin( # Changed to outerjoin
                user_interest_subq, PostCategoryScore.category == user_interest_subq.c.category
            ).filter(
                # Apply the updated filter here too, to include own posts
                or_(
                    Post.user_id == current_user.id, # Own posts
                    and_( # Other users' relevant posts
                        Post.user_id != current_user.id,
                        or_(
                            Post.privacy == PostPrivacy.PUBLIC,
                            and_(
                                Post.privacy == PostPrivacy.FRIENDS,
                                Post.user_id.in_(friend_ids)
                            )
                        )
                    )
                )
            ).group_by(Post.id, Post.timestamp)

            # Order by relevance score, then timestamp
            ordered_relevance_query = relevance_base_query.order_by(
                desc('relevance_score'), # Posts with no matching score/interest will have score 0
                desc('timestamp')
            )

            # Get total count for pagination
            # Need to count differently now because outer join might include posts 
            # that don't actually match user interests. We should count based on the 
            # visibility filter *before* the joins perhaps?
            # Let's recalculate total_items based on visibility filter only for pagination accuracy.
            visibility_filter_for_count = or_(
                Post.user_id == current_user.id,
                and_(Post.user_id != current_user.id, or_(Post.privacy == PostPrivacy.PUBLIC, and_(Post.privacy == PostPrivacy.FRIENDS, Post.user_id.in_(friend_ids))))
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
                    undefer(Post.content)
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