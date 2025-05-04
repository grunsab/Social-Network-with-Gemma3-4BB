from flask import Flask, render_template, request, redirect, url_for, flash
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
from sqlalchemy import or_ # Import 'or_' operator
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

# --- AWS S3 Configuration ---
# Best practice: Load from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET", "socialnetworkgemma")
S3_KEY = os.environ.get("S3_KEY")
S3_SECRET = os.environ.get("S3_SECRET_ACCESS_KEY")
S3_REGION = os.environ.get("S3_REGION", "us-west-2") # Default region if not set

s3_client = None
if S3_BUCKET and S3_KEY and S3_SECRET:
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=S3_KEY,
        aws_secret_access_key=S3_SECRET,
        region_name=S3_REGION
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
                "Health", "Fitness", "Beauty", "Fashion", "Pets", "Astronomy", "Mathematics", "History", "Geography", "Literature", 
                "Other"]
        self.model = "google/gemma-3-4b-it"
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
from models import User, Post, UserInterest, InviteCode, PostCategoryScore

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---
@app.route('/')
@login_required
def index():
    # Simple feed: Show all posts for now
    # Later: Implement personalized feed based on user interests
    posts = Post.query.order_by(Post.timestamp.desc()).all()
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

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        content = request.form.get('content', '') # Use .get with default
        image_file = request.files.get('image') # Get optional image file

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
                    image_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{unique_filename}"
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
            # Create the post with text, image URL, and image classification
            new_post = Post(
                content=content,
                user_id=current_user.id,
                image_url=image_url,
                classification_scores={} # Initialize as empty dict, will be populated below
            )
            db.session.add(new_post)
            db.session.flush() # Get new_post.id if needed elsewhere, post object is available

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

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post_to_delete = Post.query.get_or_404(post_id)
    if post_to_delete.author != current_user:
        # Prevent users from deleting others' posts
        flash('You do not have permission to delete this post.', 'danger')
        return redirect(url_for('index')) # Or perhaps back to the referring page

    try:
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
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    interests = UserInterest.query.filter_by(user_id=user.id).order_by(UserInterest.score.desc()).all()
    return render_template('profile.html', user=user, posts=posts, interests=interests)


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
        posts = Post.query.filter(Post.user_id != current_user.id).order_by(Post.timestamp.desc()).limit(50).all()
        flash("Explore posts to build your personalized feed!", "info")
    else:
        # Base query for posts not authored by the current user
        base_query = Post.query.filter(Post.user_id != current_user.id)
        posts_query = (base_query.filter(Post.id == PostCategoryScore.post_id).
            filter(or_(*[PostCategoryScore.category == category for category in interested_categories])).
            order_by(PostCategoryScore.score.desc()))

        # --- Fetch, Order, and Supplement ---
        # Order matched posts by their timestamp (descending), as the float score is gone
        posts = posts_query.limit(50).all()

        # Optional: Add recent posts if the feed is too small (similar to previous logic)
        if len(posts) < 10:
             # Get some recent posts to supplement, excluding ones already fetched and user's own
             existing_post_ids = [p.id for p in posts]
             recent_posts = Post.query.filter(Post.user_id != current_user.id) \
                                      .filter(Post.id.notin_(existing_post_ids)) \
                                      .order_by(Post.timestamp.desc()) \
                                      .limit(10) \
                                      .all()
             posts.extend(recent_posts)
             # Re-sort combined list by score or timestamp if desired, though extending is often fine.

    # Render the feed
    return render_template('index.html', posts=posts, feed_type="Personalized (by Category)")


if __name__ == '__main__':
    # Remove the db.create_all() call
    # with app.app_context():
    #     db.create_all() # Create database tables if they don't exist
    app.run(debug=True) # Enable debug mode for development