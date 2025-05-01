from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from openai import OpenAI
from dotenv import load_dotenv
from extensions import db, login_manager

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
from models import User, Post, UserInterest

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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
        else:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
    return render_template('register.html')

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
    with app.app_context():
        db.create_all() # Create database tables if they don't exist
    app.run(debug=True) # Enable debug mode for development 