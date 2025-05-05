from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from openai import OpenAI
from dotenv import load_dotenv
from extensions import db, login_manager, migrate
import json # Add json import
import boto3 # Add boto3 import
import uuid # Add uuid import
import base64 # Add base64 import
from sqlalchemy import or_, func, case, desc # Import 'or_' operator, func for SQL functions, case for conditional expressions, and desc for ordering
from flask_migrate import Migrate
from werkzeug.utils import secure_filename

load_dotenv()

# --- Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key') # Change in production!
# Ensure DATABASE_URL uses the correct dialect prefix for SQLAlchemy
database_url = os.environ.get('DATABASE_URL', 'sqlite:///social_network.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Method Override for RESTful methods ---
@app.before_request
def method_override():
    """Allow HTML forms to use PUT, DELETE with _method parameter."""
    if request.form and '_method' in request.form:
        method = request.form['_method'].upper()
        if method in ['PUT', 'DELETE', 'PATCH']:
            request.environ['REQUEST_METHOD'] = method  # Override the actual HTTP method

# --- AWS S3 Configuration: Now using Cloudflare R2 ---
# Best practice: Load from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET", "socialnetworkgemma")
S3_KEY = os.environ.get("S3_KEY")
S3_SECRET = os.environ.get("S3_SECRET_ACCESS_KEY")
S3_REGION = os.environ.get("S3_REGION", "auto") # Default region if not set
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
DOMAIN_NAME_IMAGES = os.environ.get("DOMAIN_NAME_IMAGES")
DEBUG = os.environ.get("DEBUG", "False") == "True"
MODEL_NAME = os.environ.get("MODEL_NAME", "google/gemma-3-4b-it")

s3_client = None
if S3_BUCKET and S3_KEY and S3_SECRET:
    s3_client = boto3.client('s3',
        endpoint_url = S3_ENDPOINT_URL,
        aws_access_key_id = S3_KEY,
        aws_secret_access_key = S3_SECRET,
        region_name = S3_REGION,
    )
    
    print(f"INFO: S3 Client initialized for bucket {S3_BUCKET} in region {S3_REGION}")
else:
    print("WARN: S3 credentials not found in environment variables. Image upload will be disabled.")

openai = OpenAI(
    api_key=os.environ.get('OPENAI_API_KEY'),
    base_url="https://api.deepinfra.com/v1/openai",
)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to login page if user is not logged in
migrate.init_app(app, db)


class GemmaClassification:
    def __init__(self):
        self.categories = ["Technology", "Travel", "Food", "Art", "Sports", "News", "Lifestyle", "Politics", "Science", "Business", "Entertainment",
                "Music", "Movies", "TV", "Gaming", "Anime", "Manga", "Work", "Gossip", "Relationships", "Philosophy", "Spirituality",
                "Health", "Fitness", "Beauty", "Fashion", "Pets", "Astronomy", "Mathematics", "History", "Geography", "Literature",  "Nature", 
                "Animals", "Weather", "Space", "Astrology", "Physics", "Chemistry", "Biology", "Animated", "Video Games", "Comics", "Drawings", "Other"]
        self.model = MODEL_NAME
        self.max_tokens = 1024
        self.response_format = {"type": "json_object"}
        self.response_content = None
        self.category_scores = {}
        self.prompt = f"""Classify the subject matter of the following information into relevant categories from the list below.
            Provide a relevance score between 0.0 and 1.0 for each category you assign (higher means more relevant).
            Return the results as a JSON object where keys are category names and values are their scores.
            Only include categories with a score > 0.1.
            If no category seems relevant or confidence is low, return an empty JSON object {{}}.
            Categories: {", ".join(self.categories)}
            JSON Output:"""


    def default_classify_function(self, messages):
        try:
            chat_completion = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=self.response_format,
                max_tokens=self.max_tokens
            )
            
            self.response_content = chat_completion.choices[0].message.content.strip()
            print(f"DEBUG: Gemma response: {self.response_content}")

            # Handle potentially malformed JSON
            try:
                self.category_scores = json.loads(self.response_content)
            except json.JSONDecodeError as je:
                print(f"ERROR: Failed to parse JSON response: {je}")
                print(f"Raw response: {self.response_content}")
                return None

            # Basic validation
            if not isinstance(self.category_scores, dict):
                print(f"ERROR: Classification result is not a dictionary: {type(self.category_scores)}")
                return None
            
            validated_scores = {}
            for category, score in self.category_scores.items():
                if category in self.categories and isinstance(score, (int, float)) and 0.0 <= score <= 1.0:
                    validated_scores[category] = float(score)
                else:
                    print(f"WARN: Invalid category '{category}' or score '{score}' received, skipping.")

            return validated_scores or {}  # Return empty dict if no valid categories found
            
        except Exception as e:
            print(f"ERROR: An error occurred during classification: {e}")
            return {}  # Return empty dict on error to avoid None-related issues

    def classify_text(self, post_content):
        """
        Classifies post content into multiple categories with scores using Gemma.
        Returns a dictionary of {category: score} or empty dict if classification fails.
        """
        if not post_content or not post_content.strip():
            print("INFO: Empty post content provided, skipping classification.")
            return {}
            
        print(f"INFO: Classifying text post: {post_content[:50]}...")
        
        # Clear and specific structured messages
        messages = [
            {"role": "system", "content": "You are a classifier that categorizes content and returns results only as a valid JSON object."},
            {"role": "user", "content": f"{self.prompt}\n\nContent to classify: {post_content}"}
        ]

        return self.default_classify_function(messages)

                
    def classify_image(self, image_data):
        """
        Classifies image data into categories with scores using the configured Gemma multimodal endpoint.
        Input: image_data (bytes)
        Returns: Dictionary of {category: score} or empty dict if classification fails.
        """
        if not image_data:
            print("ERROR: No image data provided for classification.")
            return {}
            
        print(f"INFO: Classifying image of size {len(image_data)} bytes...")
        
        try:
            # Encode the image data to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Format messages for multimodal API (DeepInfra's expected format)
            messages = [
                {"role": "system", "content": "You are a classifier that analyzes images and returns results only as a valid JSON object."},
                {"role": "user", "content": [
                    {"type": "text", "text": self.prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ]
            
            return self.default_classify_function(messages)
            
        except Exception as e:
            print(f"ERROR: Image classification failed: {e}")
            return {}


gemma_classification = GemmaClassification()


# --- Models (Defined in models.py, imported here) ---
# We will define models in a separate file later.
# For now, let's assume User and Post models exist.
from models import User, Post, UserInterest, InviteCode, PostCategoryScore, Comment, FriendRequest, FriendRequestStatus, PostPrivacy

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---
@app.route('/')
@login_required
def index():
    # Show all posts (respecting privacy settings)
    public_posts_query = Post.query.filter_by(privacy=PostPrivacy.PUBLIC)
    
    # If user is logged in, also get friends-only posts from their friends
    friends_only_posts_query = db.session.query(Post).join(
        FriendRequest, 
        (
            ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == Post.user_id)) | 
            ((FriendRequest.receiver_id == current_user.id) & (FriendRequest.sender_id == Post.user_id))
        )
    ).filter(
        FriendRequest.status == FriendRequestStatus.ACCEPTED,
        Post.privacy == PostPrivacy.FRIENDS
    )
    
    # Also include the user's own posts regardless of privacy
    own_posts_query = Post.query.filter_by(user_id=current_user.id)
    
    # Union all queries and order by timestamp
    posts = public_posts_query.union_all(friends_only_posts_query, own_posts_query).order_by(Post.timestamp.desc()).all()
    
    return render_template('index.html', posts=posts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    invite_code_str = request.args.get('invite_code')
    invite_code_obj = None

    if invite_code_str:
        invite_code_obj = InviteCode.query.filter_by(code=invite_code_str, is_used=False).first()

    # For GET request, ensure a valid code is provided in URL
    if request.method == 'GET':
        if not invite_code_obj:
            flash('Invalid or missing invite code. Registration requires a valid invite link.', 'danger')
            return redirect(url_for('login')) # Redirect to login or a specific page
        # Pass the valid code to the template
        return render_template('register.html', invite_code=invite_code_str)

    # For POST request
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        submitted_code = request.form.get('invite_code') # Get code from hidden form field

        # Re-validate the code submitted with the form
        invite_code_obj = InviteCode.query.filter_by(code=submitted_code, is_used=False).first()
        if not invite_code_obj:
            flash('Invalid or used invite code submitted with registration.', 'danger')
            # Try to get code from URL again for re-rendering, or redirect
            invite_code_str_retry = request.args.get('invite_code') or submitted_code
            if invite_code_str_retry:
                 return redirect(url_for('register', invite_code=invite_code_str_retry))
            else:
                return redirect(url_for('login'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'warning')
            # Re-render with the code
            return render_template('register.html', invite_code=submitted_code)
        else:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username,
                            password_hash=hashed_password,
                            used_invite_code=invite_code_obj.code) # Store the code used

            # Mark the invite code as used and link to the new user
            invite_code_obj.is_used = True
            invite_code_obj.used_by_id = new_user.id # Link before adding user to session

            db.session.add(new_user)
            # Add invite_code_obj changes to the session as well
            db.session.add(invite_code_obj)
            db.session.commit()

            # Important: Need to get the new user ID *after* commit
            invite_code_obj.used_by_id = new_user.id
            db.session.add(invite_code_obj)
            db.session.commit()


            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    # Fallback for GET if something went wrong (should be handled above)
    return render_template('register.html', invite_code=invite_code_str)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        content = request.form.get('content', '') # Use .get with default
        image_file = request.files.get('image') # Get optional image file
        privacy = request.form.get('privacy', 'PUBLIC') # Get privacy setting, default to PUBLIC
        
        # Debug the privacy value
        print(f"DEBUG - Privacy from form: {privacy}")
        
        if not content and not image_file:
            flash('Post cannot be empty. Please provide text or an image.', 'warning')
            return render_template('create_post.html')

        image_url = None
        image_classification_result = None

        # --- Handle Image Upload ---
        if image_file and s3_client and S3_BUCKET:
            if image_file.filename == '':
                flash('No selected file', 'warning')
                # Decide if this is an error or just means no image intended
                # return render_template('create_post.html') # Optional: uncomment if filename must exist
            else:
                # Check file size - limit to 10MB
                image_file.seek(0, os.SEEK_END)
                file_size = image_file.tell()
                image_file.seek(0)  # Reset file pointer to beginning
                
                # 10MB = 10 * 1024 * 1024 bytes
                if file_size > 10 * 1024 * 1024:  
                    flash('Image file is too large. Maximum size is 10MB.', 'warning')
                    return render_template('create_post.html')
                
                # Secure filename and generate unique key
                # filename = secure_filename(image_file.filename) # Consider using secure_filename if needed
                # Generate unique name to avoid collisions
                file_extension = os.path.splitext(image_file.filename)[1]
                unique_filename = f"images/{uuid.uuid4()}{file_extension}"

                try:
                    # Read file data for classification and upload
                    image_data = image_file.read()
                    image_file.seek(0) # Reset stream position after reading

                    # Upload to S3
                    s3_client.upload_fileobj(
                        image_file,
                        S3_BUCKET,
                        unique_filename,
                    )
                    # Construct the S3 URL (adjust based on your bucket/region/settings)
                    image_url = f"{DOMAIN_NAME_IMAGES}/{unique_filename}"
                    print(f"INFO: Image uploaded to {image_url}")

                    # Classify the image
                    image_classification_result = gemma_classification.classify_image(image_data)
                    if image_classification_result:
                         print(f"INFO: Image classified: {image_classification_result}")
                    else:
                         print("WARN: Image classification failed or returned None.")


                except Exception as e:
                    print(f"ERROR: Failed to upload image to S3: {e}")
                    flash(f'Image upload failed: {e}', 'danger')
                    # Decide if failure should prevent post creation
                    # return render_template('create_post.html') # Optional

        elif image_file and not s3_client:
            flash('Image provided, but S3 is not configured. Image was not saved.', 'warning')

        # --- Handle Text Content and Classification ---
        category_scores = None
        if content:
            category_scores = gemma_classification.classify_text(content)
            if category_scores is None:
                flash('There was an error classifying your post text. Please try again.', 'danger')
                # Decide if text classification failure should prevent post creation
                # return render_template('create_post.html') # Optional

        # --- Create and Save Post ---
        try:
            # Ensure proper enum conversion 
            try:
                privacy_enum = PostPrivacy[privacy]
                print(f"DEBUG - Converted to enum: {privacy_enum}, value: {privacy_enum.value}")
            except KeyError:
                print(f"DEBUG - Invalid privacy value: {privacy}. Defaulting to PUBLIC.")
                privacy_enum = PostPrivacy.PUBLIC
                
            # Create the post with text, image URL, image classification, and privacy setting
            new_post = Post(
                content=content,
                user_id=current_user.id,
                image_url=image_url,
                classification_scores={}, # Initialize as empty dict, will be populated below
                privacy=privacy_enum # Use the verified enum
            )
            
            db.session.add(new_post)
            db.session.flush() # Get new_post.id if needed elsewhere, post object is available
            
            # Verify the post's privacy setting after adding to session
            print(f"DEBUG - Post privacy after flush: {new_post.privacy}, value: {new_post.privacy.value}")
            
            flash_messages = []
            combined_classifications = {} # Initialize dictionary for combined scores
                            

            # --- Process Text Classification Scores ---
            if content:
                if category_scores: # Only process text scores if classification was successful
                    flash_categories = []
                    for category, score in category_scores.items():
                        combined_classifications[category] = score # Add text score

                        flash_categories.append(f"{category} ({score:.2f})")

                        # Update UserInterest for text categories
                        interest = UserInterest.query.filter_by(user_id=current_user.id, category=category).first()
                        if interest:
                            interest.score += score # Accumulate score
                        else:
                            interest = UserInterest(user_id=current_user.id, category=category, score=score)
                            db.session.add(interest)
                    if flash_categories:
                        flash_messages.append(f'Text classified: {", ".join(flash_categories)}')
                    else:
                        flash_messages.append('Text content added, but no specific categories identified.')
                else:
                     # Text content exists but classification failed or returned None
                     flash_messages.append('Text content added (classification failed or skipped).')
            elif not content and image_url:
                 flash_messages.append('Image posted.') # Message when only image exists
            # Removed redundant message for 'content and image_url' as specifics are handled below

            # --- Process Image Classification Scores ---
            if image_url: # Only process if an image was successfully uploaded
                if image_classification_result: # Check if image classification succeeded
                    flash_img_categories = []
                    for category, score in image_classification_result.items():
                        if category in combined_classifications: # Category exists from text? Average the score
                            combined_classifications[category] = (combined_classifications[category] + score) / 2.0
                        else: # New category from image
                            combined_classifications[category] = score
                        flash_img_categories.append(f"{category} ({score:.2f})")

                        # Update UserInterest for image categories
                        interest = UserInterest.query.filter_by(user_id=current_user.id, category=category).first()
                        if interest:
                            interest.score += score # Accumulate score
                        else:
                            interest = UserInterest(user_id=current_user.id, category=category, score=score)
                            db.session.add(interest)
                    if flash_img_categories:
                         flash_messages.append(f'Image classified: {", ".join(flash_img_categories)}')
                    else:
                         flash_messages.append('Image added, but no specific categories identified.')
                else:
                     flash_messages.append('Image added (classification failed or skipped).')

            # --- Save Combined Classifications (JSON) ---
            new_post.classification_scores = combined_classifications # Assign the combined dict


            for category, score in combined_classifications.items():
                # Check if the category already exists for the user
                post_category_score = PostCategoryScore(
                    post_id=new_post.id,
                    category=category,
                    score=score)
                db.session.add(post_category_score)
            
            # Combine flash messages
            if flash_messages:
                flash(' '.join(flash_messages), 'success')
            else:
                # This case shouldn't happen due to initial checks, but as a fallback:
                 flash('Post created.', 'success')


            db.session.commit()
            return redirect(url_for('index'))

        except Exception as e:
            db.session.rollback() # Rollback in case of error during commit
            print(f"ERROR: Failed to save post to database: {e}")
            flash(f'Error creating post: {e}', 'danger')
            return render_template('create_post.html') # Re-render form on error

    # GET request
    return render_template('create_post.html')

@app.route('/post/<int:post_id>', methods=['DELETE', 'POST'])
@login_required
def delete_post(post_id):
    post_to_delete = Post.query.get_or_404(post_id)
    if post_to_delete.author != current_user:
        # Prevent users from deleting others' posts
        flash('You do not have permission to delete this post.', 'danger')
        return redirect(url_for('index')) # Or perhaps back to the referring page

    try:
        # Delete associated category score entries to avoid FK constraint violation
        PostCategoryScore.query.filter_by(post_id=post_to_delete.id).delete(synchronize_session=False)
        db.session.delete(post_to_delete)
        db.session.commit()
        flash('Post deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting post: {e}', 'danger')
        print(f"Error deleting post {post_id}: {e}") # Log the error

    # Redirect back to the index page or potentially the user's profile
    # Consider redirecting to request.referrer if it's safe and available
    return redirect(url_for('index'))

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # If viewing own profile, show all posts
    if user.id == current_user.id:
        posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    # If viewing someone else's profile
    else:
        # Check if the current user is friends with the profile user
        is_friend = current_user.is_friend(user)
        
        if is_friend:
            # If friends, show both public and friends-only posts
            posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
        else:
            # If not friends, only show public posts
            posts = Post.query.filter_by(user_id=user.id, privacy=PostPrivacy.PUBLIC).order_by(Post.timestamp.desc()).all()
    
    interests = UserInterest.query.filter_by(user_id=user.id).order_by(UserInterest.score.desc()).all()

    # Determine friendship/request status for the template
    is_friend = False
    has_sent_request = False
    has_received_request = False
    if current_user.is_authenticated and current_user != user:
        is_friend = current_user.is_friend(user)
        has_sent_request = current_user.has_pending_request_to(user)
        has_received_request = current_user.has_pending_request_from(user)

    return render_template('profile.html', user=user, posts=posts, interests=interests,
                           is_friend=is_friend,
                           has_sent_request=has_sent_request,
                           has_received_request=has_received_request)

# --- Friend Request Management Routes ---
@app.route('/api/friend_requests', methods=['GET', 'POST'])
@login_required
def friend_requests():
    # GET: List pending requests
    if request.method == 'GET':
        pending_requests = current_user.get_pending_received_requests()
        return render_template('friend_requests.html', requests=pending_requests)
    
    # POST: Create a new friend request
    elif request.method == 'POST':
        # Get username from form data
        username = request.form.get('username')
        if not username:
            flash('Username is required', 'danger')
            return redirect(request.referrer or url_for('index'))
        
        user_to_request = User.query.filter_by(username=username).first_or_404()
        if current_user.send_friend_request(user_to_request):
            db.session.commit()
            flash(f'Friend request sent to {username}.', 'success')
        else:
            flash(f'Could not send friend request to {username}. You may already be friends or a request may be pending.', 'warning')
        return redirect(request.referrer or url_for('profile', username=username))

@app.route('/api/friend_requests/<int:request_id>', methods=['PUT', 'DELETE', 'POST'])
@login_required
def manage_friend_request(request_id):
    # Handle PUT: Accept/reject a request (via POST with _method=PUT)
    if request.method == 'PUT' or (request.method == 'POST' and request.form.get('_method') == 'PUT'):
        action = request.form.get('action')
        friend_request = FriendRequest.query.get_or_404(request_id)
        
        # Ensure user is the receiver
        if friend_request.receiver_id != current_user.id:
            flash('You do not have permission to manage this request', 'danger')
            return redirect(url_for('friend_requests'))
        
        sender_username = friend_request.sender.username
        
        if action == 'accept':
            if current_user.accept_friend_request(request_id):
                db.session.commit()
                flash(f'Friend request from {sender_username} accepted.', 'success')
            else:
                flash('Could not accept friend request. It might have been withdrawn or is invalid.', 'warning')
        elif action == 'reject':
            if current_user.reject_friend_request(request_id):
                db.session.commit()
                flash(f'Friend request from {sender_username} rejected.', 'success')
            else:
                flash('Could not reject friend request. It might have been withdrawn or is invalid.', 'warning')
        else:
            flash('Invalid action', 'danger')
            
        return redirect(request.referrer or url_for('friend_requests'))
    
    # Handle DELETE: Cancel a request (via POST with _method=DELETE)
    elif request.method == 'DELETE' or (request.method == 'POST' and request.form.get('_method') == 'DELETE'):
        friend_request = FriendRequest.query.get_or_404(request_id)
        
        # Ensure user is the sender
        if friend_request.sender_id != current_user.id:
            flash('You do not have permission to cancel this request', 'danger')
            return redirect(url_for('friend_requests'))
            
        receiver_username = friend_request.receiver.username
        
        if FriendRequest.query.filter_by(id=request_id).delete():
            db.session.commit()
            flash(f'Friend request to {receiver_username} cancelled.', 'success')
        else:
            flash('Could not cancel friend request.', 'warning')
            
        return redirect(request.referrer or url_for('profile', username=receiver_username))

# Friendship management
@app.route('/api/friendships/<username>', methods=['DELETE', 'POST'])
@login_required
def manage_friendship(username):
    # Handle DELETE: Remove a friendship (via POST with _method=DELETE)
    if request.method == 'DELETE' or (request.method == 'POST' and request.form.get('_method') == 'DELETE'):
        user_to_unfriend = User.query.filter_by(username=username).first_or_404()
        if current_user.unfriend(user_to_unfriend):
            db.session.commit()
            flash(f'You are no longer friends with {username}.', 'success')
        else:
            flash(f'Could not unfriend {username}. You might not have been friends.', 'warning')
        return redirect(request.referrer or url_for('profile', username=username))

# --- Invite Code Management ---
@app.route('/manage_invites', methods=['GET', 'POST'])
@login_required
def manage_invites():
    if request.method == 'POST':
        # Check if user has invites left
        if current_user.invites_left > 0:
            # Generate a new code (UUIDs are good for uniqueness)
            new_code = InviteCode(issuer_id=current_user.id)
            current_user.invites_left -= 1
            db.session.add(new_code)
            db.session.add(current_user) # Add user to session to save invites_left change
            try:
                db.session.commit()
                flash(f'New invite code generated: {new_code.code}', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error generating invite code: {e}', 'danger')
        else:
            flash('You have no invites left.', 'warning')
        return redirect(url_for('manage_invites')) # Redirect to GET after POST

    # GET request: Display existing codes and generation form
    unused_codes = InviteCode.query.filter_by(issuer_id=current_user.id, is_used=False).all()
    used_codes = InviteCode.query.join(User, InviteCode.used_by_id == User.id)\
                              .filter(InviteCode.issuer_id == current_user.id, InviteCode.is_used == True)\
                              .add_columns(User.username.label('used_by_username'))\
                              .all()

    # Process used codes to pair code object with username
    processed_used_codes = []
    for result in used_codes:
        invite_code_obj = result[0] # The InviteCode object itself
        used_by_username = result.used_by_username
        processed_used_codes.append({'code': invite_code_obj.code, 'used_by': used_by_username})


    return render_template('manage_invites.html',
                           unused_codes=unused_codes,
                           used_codes=processed_used_codes,
                           invites_left=current_user.invites_left)


# --- Feed Personalization (Basic Example) ---
@app.route('/feed')
@login_required
def personalized_feed():
    # Get top user interests (categories) based on score
    user_interests = UserInterest.query.filter_by(user_id=current_user.id).order_by(UserInterest.score.desc()).limit(5).all()
    interested_categories = [interest.category for interest in user_interests]

    if not interested_categories:
        # If no interests, show recent posts (excluding user's own), ordered by timestamp
        # But respect privacy settings
        public_posts = Post.query.filter(
            Post.user_id != current_user.id, 
            Post.privacy == PostPrivacy.PUBLIC
        ).order_by(Post.timestamp.desc())
        
        friends_posts = db.session.query(Post).join(
            FriendRequest, 
            (
                ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == Post.user_id)) | 
                ((FriendRequest.receiver_id == current_user.id) & (FriendRequest.sender_id == Post.user_id))
            )
        ).filter(
            FriendRequest.status == FriendRequestStatus.ACCEPTED,
            Post.privacy == PostPrivacy.FRIENDS,
            Post.user_id != current_user.id
        ).order_by(Post.timestamp.desc())
        
        posts = public_posts.union_all(friends_posts).order_by(Post.timestamp.desc()).limit(50).all()
        flash("Explore posts to build your personalized feed!", "info")
    else:
        # Create subquery of user interests with categories and scores
        user_interest_subq = db.session.query(
            UserInterest.category,
            UserInterest.score
        ).filter(
            UserInterest.user_id == current_user.id,
            UserInterest.category.in_(interested_categories)
        ).subquery()
        
        # Base query for public posts - now with calculated relevance
        public_base_query = db.session.query(
            Post,
            func.sum(
                PostCategoryScore.score * user_interest_subq.c.score
            ).label('relevance_score')
        ).join(
            PostCategoryScore,
            Post.id == PostCategoryScore.post_id
        ).join(
            user_interest_subq,
            PostCategoryScore.category == user_interest_subq.c.category
        ).filter(
            Post.user_id != current_user.id,
            Post.privacy == PostPrivacy.PUBLIC
        ).group_by(Post.id)
        
        # Base query for friends' posts - with relevance calculation
        friends_base_query = db.session.query(
            Post,
            func.sum(
                PostCategoryScore.score * user_interest_subq.c.score
            ).label('relevance_score')
        ).join(
            FriendRequest, 
            (
                ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == Post.user_id)) | 
                ((FriendRequest.receiver_id == current_user.id) & (FriendRequest.sender_id == Post.user_id))
            )
        ).join(
            PostCategoryScore,
            Post.id == PostCategoryScore.post_id
        ).join(
            user_interest_subq,
            PostCategoryScore.category == user_interest_subq.c.category
        ).filter(
            FriendRequest.status == FriendRequestStatus.ACCEPTED,
            Post.privacy == PostPrivacy.FRIENDS,
            Post.user_id != current_user.id
        ).group_by(Post.id)
        
        # Union queries preserving relevance_score using full select statements
        # (we can't use simple union_all here because we need to preserve relevance_score)
        combined_query = public_base_query.union_all(friends_base_query)
        
        # Order by relevance score (descending) then by timestamp
        posts_with_scores = combined_query.order_by(
            desc('relevance_score'),
            Post.timestamp.desc()
        ).limit(50).all()
        
        # Extract just the Post objects from the result tuples
        posts = [post_tuple[0] for post_tuple in posts_with_scores]
        
        # If we don't have enough posts, add some recent ones
        if len(posts) < 10:
            existing_post_ids = [p.id for p in posts]
            
            # Get recent public posts
            recent_public_posts = Post.query.filter(
                Post.user_id != current_user.id,
                Post.privacy == PostPrivacy.PUBLIC,
                ~Post.id.in_(existing_post_ids)
            ).order_by(Post.timestamp.desc()).limit(5).all()
            
            # Get recent friends' posts
            recent_friends_posts = db.session.query(Post).join(
                FriendRequest, 
                (
                    ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == Post.user_id)) | 
                    ((FriendRequest.receiver_id == current_user.id) & (FriendRequest.sender_id == Post.user_id))
                )
            ).filter(
                FriendRequest.status == FriendRequestStatus.ACCEPTED,
                Post.privacy == PostPrivacy.FRIENDS,
                Post.user_id != current_user.id,
                ~Post.id.in_(existing_post_ids)
            ).order_by(Post.timestamp.desc()).limit(5).all()
            
            posts.extend(recent_public_posts)
            posts.extend(recent_friends_posts)

    # We no longer need to sort in Python - it's handled by the SQL query
    return render_template('index.html', posts=posts, feed_type="Personalized")

# --- Comment Routes ---
@app.route('/post/<int:post_id>/comments', methods=['GET', 'POST'])
@login_required
def comments(post_id):
    post = Post.query.get_or_404(post_id)
    
    if request.method == 'POST':
        content = request.form.get('content')
        
        if not content:
            flash('Comment cannot be empty', 'warning')
            return redirect(url_for('index'))
        
        new_comment = Comment(
            content=content,
            user_id=current_user.id,
            post_id=post_id
        )
        
        db.session.add(new_comment)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests
            return jsonify({
                'id': new_comment.id,
                'content': new_comment.content,
                'author': current_user.username,
                'timestamp': new_comment.timestamp.strftime('%Y-%m-%d %H:%M'),
                'is_author': True
            })
        else:
            # For regular form submissions
            return redirect(url_for('index'))
    else:  # GET request
        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.timestamp).all()
        
        comments_data = []
        for comment in comments:
            author = User.query.get(comment.user_id)
            comments_data.append({
                'id': comment.id,
                'content': comment.content,
                'author': author.username,
                'timestamp': comment.timestamp.strftime('%Y-%m-%d %H:%M'),
                'is_author': author.id == current_user.id
            })
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests
            return jsonify(comments_data)
        else:
            # For regular page requests
            return render_template('comments.html', comments=comments, post=post)

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    
    # Ensure only the author can delete their comment
    if comment.user_id != current_user.id:
        flash('You do not have permission to delete this comment', 'danger')
        return redirect(url_for('index'))
    
    db.session.delete(comment)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # For AJAX requests
        return jsonify({'success': True})
    else:
        # For regular form submissions
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=DEBUG)