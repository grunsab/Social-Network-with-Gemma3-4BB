from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from openai import OpenAI
from dotenv import load_dotenv
from extensions import db, login_manager, migrate

load_dotenv()

# --- Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key') # Change in production!
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///social_network.db')
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
    Placeholder function to simulate post classification.
    Replace with actual Gemma model integration.
    Returns a category string.
    """
    print(f"INFO: Classifying post (placeholder): {post_content[:50]}...")

    chat_completion = openai.chat.completions.create(
        model="google/gemma-3-4b-it",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that classifies posts into categories. The categories are: Technology, Travel, Food, Art, Sports, News, Lifestyle, Other. Return with only the category name."},
            {"role": "user", "content": post_content}],
    )

    return chat_completion.choices[0].message.content.strip()


# --- Models (Defined in models.py, imported here) ---
# We will define models in a separate file later.
# For now, let's assume User and Post models exist.
from models import User, Post, UserInterest, InviteCode

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
            # Classify the post using our placeholder
            category = classify_post_with_gemma(content)

            # Create and save the post
            new_post = Post(content=content, user_id=current_user.id, category=category)
            db.session.add(new_post)

            # Learn user interest (simple implementation)
            # Check if interest already exists
            interest = UserInterest.query.filter_by(user_id=current_user.id, category=category).first()
            if interest:
                interest.score += 1 # Increment score if interest exists
            else:
                # Create new interest record
                interest = UserInterest(user_id=current_user.id, category=category, score=1)
                db.session.add(interest)

            db.session.commit()
            flash(f'Post created and classified as: {category}')
            return redirect(url_for('index'))
        else:
            flash('Post content cannot be empty')
    return render_template('create_post.html')

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
    user_interests = UserInterest.query.filter_by(user_id=current_user.id).order_by(UserInterest.score.desc()).limit(5).all()
    interested_categories = [interest.category for interest in user_interests]

    if not interested_categories:
        # If no interests, show recent posts
        posts = Post.query.order_by(Post.timestamp.desc()).limit(50).all()
        flash("Explore posts to build your personalized feed!")
    else:
        # Fetch posts matching the user's top interests
        posts = Post.query.filter(Post.category.in_(interested_categories)).order_by(Post.timestamp.desc()).limit(50).all()
        # Maybe add some recent posts not in categories if the feed is too small?
        if len(posts) < 10:
             # Get some recent posts to supplement, excluding ones already fetched
             existing_post_ids = [p.id for p in posts]
             recent_posts = Post.query.filter(Post.id.notin_(existing_post_ids)).order_by(Post.timestamp.desc()).limit(10).all()
             posts.extend(recent_posts)


    return render_template('index.html', posts=posts, feed_type="Personalized")


if __name__ == '__main__':
    # Remove the db.create_all() call
    # with app.app_context():
    #     db.create_all() # Create database tables if they don't exist
    app.run(debug=True) # Enable debug mode for development 