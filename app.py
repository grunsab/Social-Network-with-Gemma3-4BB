from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from openai import OpenAI
from dotenv import load_dotenv
from extensions import db, login_manager, migrate
import json # Add json import

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

openai = OpenAI(
    api_key=os.environ.get('OPENAI_API_KEY'),
    base_url="https://api.deepinfra.com/v1/openai",
)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to login page if user is not logged in
migrate.init_app(app, db)

def classify_post_with_gemma(post_content):
    """
    Classifies post content into multiple categories with scores using Gemma.
    Returns a dictionary of {category: score} or None if classification fails.
    """
    print(f"INFO: Classifying post: {post_content[:50]}...")
    categories = ["Technology", "Travel", "Food", "Art", "Sports", "News", "Lifestyle", "Politics", "Science", "Business", "Entertainment",
                  "Music", "Movies", "TV", "Gaming", "Anime", "Manga", "Work", "Gossip", "Relationships", "Philosophy", "Spirituality",
                   "Health", "Fitness", "Beauty", "Fashion", "Pets", "Astronomy", "Mathematics", "History", "Geography", "Literature", "Other"]
    prompt = f"""Classify the following post content into relevant categories from the list below.
    Provide a relevance score between 0.0 and 1.0 for each category you assign (higher means more relevant).
    Return the results as a JSON object where keys are category names and values are their scores.
    Only include categories with a score > 0.1.
    If no category seems relevant or confidence is low, return an empty JSON object {{}}.
    Categories: {", ".join(categories)}
    Post Content: {post_content}
    JSON Output:"""

    try:
        chat_completion = openai.chat.completions.create(
            model="google/gemma-3-4b-it", # Or another suitable model
            messages=[
                # System prompt can be simpler if instructions are in user prompt
                {"role": "system", "content": "You are an assistant that classifies posts into categories and provides relevance scores as a JSON object."}, 
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"} # Request JSON output if model supports it
        )

        response_content = chat_completion.choices[0].message.content.strip()
        print(f"DEBUG: Gemma response: {response_content}")

        # Parse the JSON response
        category_scores = json.loads(response_content)

        # Basic validation (ensure it's a dict and scores are numbers)
        if not isinstance(category_scores, dict):
            print("ERROR: Classification result is not a dictionary.")
            return None
        
        validated_scores = {}
        for category, score in category_scores.items():
            if category in categories and isinstance(score, (int, float)) and 0.0 <= score <= 1.0:
                 validated_scores[category] = float(score)
            else:
                print(f"WARN: Invalid category '{category}' or score '{score}' received, skipping.")

        if not validated_scores:
            print("INFO: No relevant categories found or low confidence.")
            # Optionally assign 'Other' if needed, or return None/empty dict
            # return {"Other": 0.1}
            return {}

        return validated_scores

    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON response from classification model: {e}")
        # It's likely response_content exists if JSON decoding failed, but check just in case.
        logged_response = locals().get('response_content', 'Response content unavailable')
        print(f"Response was: {logged_response}")
        return None
    except Exception as e:
        print(f"ERROR: An error occurred during post classification: {e}")
        return None


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
        content = request.form['content']
        if content:
            # Classify the post using the updated function
            category_scores = classify_post_with_gemma(content)

            if category_scores is None:
                flash('There was an error classifying your post. Please try again.', 'danger')
                return render_template('create_post.html')

            # Create the post *without* the category field
            new_post = Post(content=content, user_id=current_user.id)
            db.session.add(new_post)
            # We need to flush to get the new_post.id before creating PostCategoryScore
            db.session.flush()

            if not category_scores: # Handle empty dict (no categories found)
                flash('Post created, but no specific categories were identified.', 'info')
            else:
                flash_categories = []
                # Add PostCategoryScore entries and update UserInterest
                for category, score in category_scores.items():
                    # Create score entry for the post
                    post_cat_score = PostCategoryScore(post_id=new_post.id, category=category, score=score)
                    db.session.add(post_cat_score)
                    flash_categories.append(f"{category} ({score:.2f})")

                    # Update UserInterest
                    interest = UserInterest.query.filter_by(user_id=current_user.id, category=category).first()
                    if interest:
                        # Simple weighted update: add the score of the new post
                        # More complex logic could be used (e.g., decaying older scores)
                        interest.score += score
                    else:
                        # Create new interest record with the score from this post
                        interest = UserInterest(user_id=current_user.id, category=category, score=score)
                        db.session.add(interest)
                
                flash(f'Post created and classified: {", ".join(flash_categories)}', 'success')

            db.session.commit()
            return redirect(url_for('index'))
        else:
            flash('Post content cannot be empty!', 'warning')
            return render_template('create_post.html')
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
        # If no interests, show recent posts (excluding user's own)
        posts = Post.query.filter(Post.user_id != current_user.id).order_by(Post.timestamp.desc()).limit(50).all()
        flash("Explore posts to build your personalized feed!", "info")
    else:
        # Fetch posts that have a score in ANY of the user's top interested categories,
        # EXCLUDING the user's own posts.
        # We use distinct() to avoid duplicate posts if a post matches multiple categories.
        posts_query = db.session.query(Post).distinct() \
            .join(PostCategoryScore, Post.id == PostCategoryScore.post_id) \
            .filter(PostCategoryScore.category.in_(interested_categories)) \
            .filter(Post.user_id != current_user.id) # Exclude user's own posts

        posts = posts_query.order_by(Post.timestamp.desc()).limit(50).all()


        # Maybe add some recent posts not in categories if the feed is too small?
        if len(posts) < 10:
             # Get some recent posts to supplement, excluding ones already fetched and user's own
             existing_post_ids = [p.id for p in posts]
             # Ensure we don't fetch posts already in the list OR user's own posts
             recent_posts = Post.query.filter(Post.user_id != current_user.id) \
                                      .filter(Post.id.notin_(existing_post_ids)) \
                                      .order_by(Post.timestamp.desc()) \
                                      .limit(10) \
                                      .all()
             posts.extend(recent_posts)

    return render_template('index.html', posts=posts, feed_type="Personalized")


if __name__ == '__main__':
    # Remove the db.create_all() call
    # with app.app_context():
    #     db.create_all() # Create database tables if they don't exist
    app.run(debug=True) # Enable debug mode for development 