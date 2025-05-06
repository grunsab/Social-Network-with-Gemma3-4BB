from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
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
from sqlalchemy import or_, func, case, desc, union_all # Import 'or_' operator, func for SQL functions, case for conditional expressions, desc for ordering, and union_all
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload, undefer
from flask_restful import Api # <<< Add this import

# <<< Import Auth Resources >>>
from resources.auth import UserRegistration, UserLogin
# <<< Import Post Resources >>>
from resources.post import PostListResource, PostResource
# <<< Import Comment Resources >>>
from resources.comment import CommentListResource, CommentResource
# <<< Import Profile Resource >>>
from resources.profile import ProfileResource
# <<< Import Friendship Resources >>>
from resources.friendship import FriendRequestListResource, FriendRequestResource, FriendshipResource
# <<< Import Feed Resource >>>
from resources.feed import FeedResource
# <<< Import Category Resource >>>
from resources.category import CategoryResource
# <<< Import Invite Resource >>>
from resources.invite import InviteResource

# Load blocked categories
BLOCKED_CATEGORIES = set()
blocked_categories_path = os.path.join(os.path.dirname(__file__), 'blocked_categories.json')
try:
    with open(blocked_categories_path, 'r') as f:
        BLOCKED_CATEGORIES = set(json.load(f))
    print(f"INFO: Loaded {len(BLOCKED_CATEGORIES)} blocked categories: {BLOCKED_CATEGORIES}")
except FileNotFoundError:
    print(f"WARN: blocked_categories.json not found at {blocked_categories_path}. No categories will be blocked.")
except json.JSONDecodeError:
    print(f"ERROR: Could not decode JSON from {blocked_categories_path}. No categories will be blocked.")

load_dotenv()

# --- Configuration ---
app = Flask(__name__, static_folder='frontend/dist', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key') # Change in production!
# Ensure DATABASE_URL uses the correct dialect prefix for SQLAlchemy
database_url = os.environ.get('DATABASE_URL', 'sqlite:///social_network.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# <<< Load S3/R2 config and store in app.config >>>
app.config['S3_BUCKET'] = os.environ.get("S3_BUCKET", "socialnetworkgemma")
app.config['S3_KEY'] = os.environ.get("S3_KEY")
app.config['S3_SECRET'] = os.environ.get("S3_SECRET_ACCESS_KEY")
app.config['S3_REGION'] = os.environ.get("S3_REGION", "auto")
app.config['S3_ENDPOINT_URL'] = os.environ.get("S3_ENDPOINT_URL")
app.config['DOMAIN_NAME_IMAGES'] = os.environ.get("DOMAIN_NAME_IMAGES")

# <<< Load other config >>>
app.config['DEBUG'] = os.environ.get("DEBUG", "False") == "True"
app.config['MODEL_NAME'] = os.environ.get("MODEL_NAME", "google/gemma-3-4b-it")
app.config['FRONTEND_URL'] = os.environ.get('FRONTEND_URL', '') # Add frontend URL config

api = Api(app) # Initialize Flask-Restful

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
# <<< Removed direct variable assignments, use app.config now >>>
# S3_BUCKET = app.config['S3_BUCKET']
# ... etc ...

# <<< Initialize s3_client and store in app.config >>>
s3_client = None
if app.config['S3_BUCKET'] and app.config['S3_KEY'] and app.config['S3_SECRET']:
    s3_client = boto3.client('s3',
        endpoint_url = app.config['S3_ENDPOINT_URL'],
        aws_access_key_id = app.config['S3_KEY'],
        aws_secret_access_key = app.config['S3_SECRET'],
        region_name = app.config['S3_REGION'],
    )
    app.config['S3_CLIENT'] = s3_client # Store client in config
    print(f"INFO: S3 Client initialized for bucket {app.config['S3_BUCKET']} in region {app.config['S3_REGION']}")
else:
    app.config['S3_CLIENT'] = None
    print("WARN: S3 credentials not found in environment variables. Image upload will be disabled.")

# <<< Initialize OpenAI client >>>
openai_client = OpenAI(
    api_key=os.environ.get('OPENAI_API_KEY'),
    base_url="https://api.deepinfra.com/v1/openai",
)
app.config['OPENAI_CLIENT'] = openai_client # Store client in config

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to login page if user is not logged in
migrate.init_app(app, db)

# <<< Add API Resources >>>
api.add_resource(UserRegistration, '/api/v1/register')
api.add_resource(UserLogin, '/api/v1/login') 
api.add_resource(PostListResource, '/api/v1/posts') 
api.add_resource(PostResource, '/api/v1/posts/<int:post_id>') 
api.add_resource(CommentListResource, '/api/v1/posts/<int:post_id>/comments') # GET list, POST create
api.add_resource(CommentResource, '/api/v1/comments/<int:comment_id>') # DELETE single
api.add_resource(ProfileResource, '/api/v1/profiles/<string:username>') # GET profile data
api.add_resource(FriendRequestListResource, '/api/v1/friend-requests') # GET received pending, POST send request
api.add_resource(FriendRequestResource, '/api/v1/friend-requests/<int:request_id>') # PUT accept/reject, DELETE cancel sent
api.add_resource(FriendshipResource, '/api/v1/friendships/<int:user_id>') # DELETE unfriend
api.add_resource(FeedResource, '/api/v1/feed') # GET personalized feed
api.add_resource(CategoryResource, '/api/v1/categories/<string:category_name>/posts') # GET posts for category
api.add_resource(InviteResource, '/api/v1/invites') # GET list/details, POST generate

# <<< Initialize GemmaClassification and store in app.config >>>
class GemmaClassification:
    def __init__(self, app_config):
        # Load categories from JSON file
        categories_path = os.path.join(os.path.dirname(__file__), 'categories.json')
        try:
            with open(categories_path, 'r') as f:
                self.categories = json.load(f)
        except FileNotFoundError:
            print(f"Error: categories.json not found at {categories_path}")
            self.categories = ["Technology", "Travel", "Food", "Art", "Sports", "News", "Lifestyle", "Politics", "Science", "Business", "Entertainment"]
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {categories_path}")
            self.categories = ["Technology", "Travel", "Food", "Art", "Sports", "News", "Lifestyle", "Politics", "Science", "Business", "Entertainment"]

        self.model = app_config.get('MODEL_NAME', 'google/gemma-3-4b-it') # Get from config
        self.openai_client = app_config.get('OPENAI_CLIENT') # Get client from config
        self.max_tokens = 1024
        self.response_format = {"type": "json_object"}
        self.prompt = f"""Classify the subject matter of the following information into relevant categories from the list below.
            Provide a relevance score between 0.0 and 1.0 for each category you assign (higher means more relevant).
            Return the results as a JSON object where keys are category names and values are their scores.
            Only include categories with a score > 0.1.
            If no category seems relevant or confidence is low, return an empty JSON object {{}}.
            Categories: {", ".join(self.categories)}
            JSON Output:"""

    def default_classify_function(self, messages):
        if not self.openai_client:
            print("ERROR: OpenAI client not configured for classification.")
            return {}
        try:
            chat_completion = self.openai_client.chat.completions.create(
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

# Instantiate GemmaClassification AFTER app config is populated
app.config['GEMMA_CLASSIFICATION'] = GemmaClassification(app.config)

# --- Models (Defined in models.py, imported here) ---
# We will define models in a separate file later.
# For now, let's assume User and Post models exist.
from models import User, Post, UserInterest, InviteCode, PostCategoryScore, Comment, FriendRequest, FriendRequestStatus, PostPrivacy

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    from models import User # Import here to avoid circular dependency if models import app
    return User.query.get(int(user_id))

# --- Serve React App ---

# Remove the custom 404 handler for serving index.html
# @app.errorhandler(404)
# def not_found(e):
#     if request.path.startswith('/api/'):
#         return jsonify({"message": "Resource not found"}), 404
#     # Serve index.html for frontend routes
#     index_path = os.path.join(app.static_folder, 'index.html')
#     if not os.path.exists(index_path):
#          return "React frontend not built yet. Run 'npm run build' in the frontend directory.", 404
#     return send_from_directory(app.static_folder, 'index.html')

# Serve React's index.html for the root path
@app.route('/')
def serve_index():
    index_path = os.path.join(app.static_folder, 'index.html')
    if not os.path.exists(index_path):
        # Consider a more user-friendly message or logging
        return "Error: index.html not found in static folder. Build the frontend first!", 404
    return send_from_directory(app.static_folder, 'index.html')

# Serve React's index.html for any other path that is not an API endpoint
# This MUST be defined AFTER the API routes
@app.route('/<path:path>')
def serve_react_app(path): # path variable is required by Flask but not used directly here
    # Check if the path corresponds to a static file in the build assets
    # If it exists, Flask's static file handling should serve it automatically 
    # due to static_url_path=''. If not, serve index.html for client-side routing.
    
    # Check if the path requested exists as a file in the static folder.
    # This prevents serving index.html for valid asset requests (e.g. /assets/main.js)
    # that might somehow miss Flask's direct static serving.
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        # Serve index.html for all other paths, allowing React Router to handle them
        index_path = os.path.join(app.static_folder, 'index.html')
        if not os.path.exists(index_path):
             return "Error: index.html not found. Build the frontend first!", 404
        return send_from_directory(app.static_folder, 'index.html')

# --- Friend Request Management Routes ---
# @app.route('/api/friend_requests', methods=['GET', 'POST'])
# @login_required
# def friend_requests():
#     ...
# 
# @app.route('/api/friend_requests/<int:request_id>', methods=['PUT', 'DELETE', 'POST'])
# @login_required
# def manage_friend_request(request_id):
#     ...

# Friendship management
# @app.route('/api/friendships/<username>', methods=['DELETE', 'POST'])
# @login_required
# def manage_friendship(username):
#     ...

# --- Invite Code Management ---
# @app.route('/manage_invites', methods=['GET', 'POST'])
# @login_required
# def manage_invites():
#    ...

if __name__ == '__main__':
    # Make sure host is set to 0.0.0.0 to be accessible externally if needed
    app.run(host='0.0.0.0', debug=app.config.get('DEBUG', False), port=5000)