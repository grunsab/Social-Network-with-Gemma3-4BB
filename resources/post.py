from flask import request, jsonify, current_app
from flask_restful import Resource, reqparse, fields, marshal_with
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage # Import FileStorage for reqparse
import uuid
import os
from sqlalchemy.orm import joinedload

from models import db, User, Post, PostCategoryScore, UserInterest, PostPrivacy, FriendRequest, FriendRequestStatus
# Import the formatter function
from utils import format_text_with_ampersounds 

# We might need access to the S3 client and GemmaClassification instance from app.py
# This might require passing app context or using current_app

# Parser for post creation
post_parser = reqparse.RequestParser()
post_parser.add_argument('content', type=str, required=False, help='Post content (text)', location='form')
post_parser.add_argument('image', type=FileStorage, required=False, help='Image file for the post', location='files')
post_parser.add_argument('privacy', type=str, default='PUBLIC', choices=([p.name for p in PostPrivacy]), help='Post privacy setting (PUBLIC, FRIENDS)', location='form')

list_posts_parser = reqparse.RequestParser() # For GET list
list_posts_parser.add_argument('page', type=int, default=1, help='Page number for pagination', location='args')
list_posts_parser.add_argument('per_page', type=int, default=20, help='Number of posts per page', location='args')

# --- Field definitions for Marshaling --- 
# Define how nested objects should be serialized
author_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'profile_picture': fields.String # Add profile pic if needed
}

# Formatted content field for Ampersounds
class FormattedContent(fields.Raw):
    def format(self, value):
        # 'value' here is the post object itself, passed via attribute
        post_object = value
        if not post_object.content or not post_object.author:
            return post_object.content # Return original content if no author or content
        return format_text_with_ampersounds(post_object.content, post_object.author.username)

post_fields = {
    'id': fields.Integer,
    'content': FormattedContent(attribute=lambda x: x), # Pass the whole post object to our custom field
    'image_url': fields.String,
    'timestamp': fields.DateTime(dt_format='iso8601'),
    'privacy': fields.String(attribute='privacy.name'), # Get enum name
    'author': fields.Nested(author_fields), # Nested author data
    'classification_scores': fields.Raw(attribute='classification_scores'), # Keep as JSON object
    # Add comments count or other fields later if needed
    # 'comments_count': fields.Integer(attribute=lambda x: len(x.comments)) # Example
}

post_list_fields = {
    'posts': fields.List(fields.Nested(post_fields)),
    'page': fields.Integer,
    'per_page': fields.Integer,
    'total': fields.Integer # Total number of posts matching query (before pagination)
}

class PostListResource(Resource):
    @login_required
    def post(self):
        args = post_parser.parse_args()
        content = args['content']
        image_file = args['image']
        privacy_str = args['privacy']

        # Access app context items
        s3_client = current_app.config.get('S3_CLIENT') # Assume s3_client is stored in app config or context
        gemma_classification = current_app.config.get('GEMMA_CLASSIFIER') # Same assumption
        s3_bucket = current_app.config.get('S3_BUCKET')
        domain_name_images = current_app.config.get('DOMAIN_NAME_IMAGES')

        if not content and not image_file:
            return {'message': 'Post cannot be empty. Provide text or an image.'}, 400

        image_url = None
        image_classification_result = None

        # --- Handle Image Upload --- (Adapted from app.py/create_post)
        if image_file and s3_client and s3_bucket:
            if image_file.filename == '':
                # No file selected, but 'image' key might be present
                pass # Allow posts with just text
            else:
                # Check file size - limit to 10MB
                image_file.seek(0, os.SEEK_END)
                file_size = image_file.tell()
                image_file.seek(0)
                if file_size > 10 * 1024 * 1024:
                    return {'message': 'Image file too large (max 10MB)'}, 413 # Payload Too Large

                file_extension = os.path.splitext(image_file.filename)[1]
                unique_filename = f"images/{uuid.uuid4()}{file_extension}"

                try:
                    image_data = image_file.read()
                    image_file.seek(0)

                    s3_client.upload_fileobj(
                        image_file,
                        s3_bucket,
                        unique_filename,
                    )
                    image_url = f"{domain_name_images}/{unique_filename}"
                    print(f"INFO: Image uploaded to {image_url}")

                    # Classify the image (ensure gemma_classification is available)
                    if gemma_classification:
                        image_classification_result = gemma_classification.classify_image(image_data)
                        if image_classification_result:
                            print(f"INFO: Image classified: {image_classification_result}")
                        else:
                            print("WARN: Image classification failed or returned None.")
                    else:
                        print("WARN: GemmaClassification not available for image.")

                except Exception as e:
                    print(f"ERROR: Failed to upload image to S3: {e}")
                    return {'message': f'Image upload failed: {e}'}, 500

        elif image_file and not s3_client:
            print('WARN: Image provided, but S3 is not configured. Image was not saved.')
            # Decide if this should be an error or just a warning message in response
            # return {'message': 'S3 not configured, image not saved'}, 400

        # --- Handle Text Content and Classification ---
        text_classification_result = None
        if content and gemma_classification:
            text_classification_result = gemma_classification.classify_text(content)
            if text_classification_result is None:
                print('WARN: Text classification failed or returned None.')
                 # Decide if this should be an error
                 # return {'message': 'Text classification failed'}, 500
            else:
                print(f"INFO: Text classified: {text_classification_result}")
        elif content and not gemma_classification:
            print("WARN: GemmaClassification not available for text.")

        # --- Create and Save Post ---
        try:
            privacy_enum = PostPrivacy[privacy_str]
            new_post = Post(
                content=content if content else "", # Ensure content is not None
                user_id=current_user.id,
                image_url=image_url,
                classification_scores={}, # To be populated
                privacy=privacy_enum
            )
            db.session.add(new_post)
            db.session.flush() # Need post ID for scores

            combined_classifications = {}
            # Process Text Classification
            if text_classification_result:
                for category, score in text_classification_result.items():
                    combined_classifications[category] = score
                    # Update UserInterest
                    interest = UserInterest.query.filter_by(user_id=current_user.id, category=category).first()
                    if interest: interest.score += score
                    else: db.session.add(UserInterest(user_id=current_user.id, category=category, score=score))

            # Process Image Classification
            if image_classification_result:
                for category, score in image_classification_result.items():
                    # Average score if category exists from text
                    combined_classifications[category] = (combined_classifications.get(category, 0) + score) / (2.0 if category in combined_classifications else 1.0)
                    # Update UserInterest
                    interest = UserInterest.query.filter_by(user_id=current_user.id, category=category).first()
                    if interest: interest.score += score # Consider averaging or different logic here too
                    else: db.session.add(UserInterest(user_id=current_user.id, category=category, score=score))

            # Save Combined Classifications (JSON and relational)
            new_post.classification_scores = combined_classifications
            for category, score in combined_classifications.items():
                db.session.add(PostCategoryScore(post_id=new_post.id, category=category, score=score))

            db.session.commit()

            # Return created post data (or just success)
            # Need a way to serialize the post object properly
            return {
                'message': 'Post created successfully',
                'post': {
                    'id': new_post.id,
                    'content': new_post.content,
                    'image_url': new_post.image_url,
                    'privacy': new_post.privacy.name,
                    'timestamp': new_post.timestamp.isoformat(),
                    'author_username': new_post.author.username, # Assumes relationship loaded
                    'classification_scores': new_post.classification_scores
                }
             }, 201

        except Exception as e:
            db.session.rollback()
            print(f"ERROR: Failed to save post to database: {e}")
            return {'message': f'Error creating post: {e}'}, 500

    @login_required
    @marshal_with(post_list_fields) # Use marshal_with to automatically format output
    def get(self):
        args = list_posts_parser.parse_args()
        page = args['page']
        per_page = args['per_page']
        
        blocked_categories = current_app.config.get('BLOCKED_CATEGORIES', set())

        # --- Query Building (adapted from app.py/index) ---
        # Base query - Eager load author and scores needed for filtering/display
        base_query = Post.query.options(
            joinedload(Post.author), 
            joinedload(Post.category_scores)
        )

        # 1. Public Posts
        public_posts_q = base_query.filter(Post.privacy == PostPrivacy.PUBLIC)

        # 2. Friends' Posts (Friends Only)
        # Find IDs of friends
        friend_ids = current_user.get_friend_ids() # Assumes User model has get_friend_ids()
        friends_posts_q = base_query.filter(
            Post.user_id.in_(friend_ids),
            Post.privacy == PostPrivacy.FRIENDS
        )

        # 3. Own Posts
        own_posts_q = base_query.filter(Post.user_id == current_user.id)

        # Combine queries using union (might need adjustment depending on exact SQLalchemy version/behavior)
        # A simpler approach for filtering might be to fetch all potentially visible posts
        # and filter in Python, especially if the total number isn't massive.
        # Let's try filtering directly in the query:
        
        combined_filter = (
            (Post.privacy == PostPrivacy.PUBLIC) |
            (Post.user_id == current_user.id) |
            (
                (Post.privacy == PostPrivacy.FRIENDS) &
                Post.user_id.in_(friend_ids)
            )
        )
        
        # Initial query with visibility filter
        visible_posts_query = base_query.filter(combined_filter)
        
        # Apply category blocking - This is tricky with SQL efficiently.
        # It's often easier to filter after fetching or use a subquery/CTE if performance demands it.
        # Simple Python filter after query:
        paginated_query = visible_posts_query.order_by(Post.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        all_posts_in_page = paginated_query.items
        total_posts_count = paginated_query.total # Get total count from pagination object
        
        # Filter out blocked categories in Python
        filtered_posts = []
        for post in all_posts_in_page:
            post_categories = {score.category for score in post.category_scores}
            if not post_categories.intersection(blocked_categories):
                filtered_posts.append(post)

        # Marshal the final list of posts
        # The marshal_with decorator handles the final structure
        return {
            'posts': filtered_posts,
            'page': page,
            'per_page': per_page,
            'total': total_posts_count # Note: This total is *before* category filtering.
                                        # Accurate total requires counting after filtering, more complex query.
        }

class PostResource(Resource):
    @login_required
    @marshal_with(post_fields) # Use marshal_with for single post too
    def get(self, post_id):
        # Logic for fetching a single post by ID
        # Check permissions based on privacy and friendship
        post = Post.query.get_or_404(post_id)

        # Permission check (simplified example)
        is_author = post.user_id == current_user.id
        is_public = post.privacy == PostPrivacy.PUBLIC
        is_friend = False
        if not is_public and not is_author:
            # Check friendship if post is friends-only and user is not author
            is_friend = current_user.is_friend(post.author) # Assumes is_friend method exists

        if not is_public and not is_author and not is_friend:
             return {'message': 'You do not have permission to view this post'}, 403

        # Return post data (need serialization)
        return post # Marshal handles the conversion

    @login_required
    def delete(self, post_id):
        # Logic for deleting a post (migrated from delete_post route)
        post_to_delete = Post.query.get_or_404(post_id)
        if post_to_delete.user_id != current_user.id:
            # Prevent users from deleting others' posts
            return {'message': 'You do not have permission to delete this post.'}, 403 # Forbidden

        try:
            # Delete associated category score entries first
            PostCategoryScore.query.filter_by(post_id=post_to_delete.id).delete(synchronize_session='fetch') # Changed synchronize_session strategy
            
            # Delete associated comments (assuming Comment model has post_id)
            from models import Comment # Import here or at top if not already
            Comment.query.filter_by(post_id=post_to_delete.id).delete(synchronize_session='fetch')

            db.session.delete(post_to_delete)
            db.session.commit()
            return {'message': 'Post deleted successfully.'}, 200 # OK or 204 No Content
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting post {post_id}: {e}") # Log the error
            return {'message': f'Error deleting post: {e}'}, 500

    @login_required
    @marshal_with(post_fields)
    def put(self, post_id):
        # Logic for updating a post (optional)
        # Check ownership, parse updates, save changes
        # Example: Update content and privacy
        update_parser = reqparse.RequestParser()
        update_parser.add_argument('content', type=str, required=False, location='json')
        update_parser.add_argument('privacy', type=str, choices=([p.name for p in PostPrivacy]), required=False, location='json')
        args = update_parser.parse_args()

        post_to_update = Post.query.get_or_404(post_id)
        if post_to_update.user_id != current_user.id:
            return {'message': 'You do not have permission to update this post.'}, 403

        updated = False
        if args['content'] is not None:
            post_to_update.content = args['content']
            # Note: Re-classification might be needed if content changes significantly
            updated = True
        
        if args['privacy'] is not None:
            try:
                post_to_update.privacy = PostPrivacy[args['privacy']]
                updated = True
            except KeyError:
                 return {'message': f'Invalid privacy value: {args["privacy"]}'}, 400

        if not updated:
            return {'message': 'No update data provided'}, 400
        
        try:
            db.session.commit()
             # Return updated post data (need serialization)
            db.session.refresh(post_to_update) # Refresh to get latest state after commit if needed
            return post_to_update # Return the updated post object
        except Exception as e:
            db.session.rollback()
            print(f"Error updating post {post_id}: {e}")
            return {'message': f'Error updating post: {e}'}, 500 