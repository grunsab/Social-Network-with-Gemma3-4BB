import os
import json
import uuid
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_login import login_required, current_user
from flask_restful import Api
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, func, case, desc, union_all
from sqlalchemy.orm import joinedload, undefer
from dotenv import load_dotenv
import boto3
from openai import OpenAI

# Import extensions and models AFTER defining configurations
from extensions import db, login_manager, migrate
# Import models here if they don't depend on the app instance directly at import time
# If models.py imports 'app', this needs further adjustment.
# Corrected imports: Use InviteCode instead of Invite.
# Removed Profile, Friendship, and Category as they don't exist as distinct models.
from models import User, Post, Comment, FriendRequest, InviteCode, UserInterest

# Import Resources AFTER defining configurations and extensions
from resources.auth import UserRegistration, UserLogin
from resources.post import PostListResource, PostResource
from resources.comment import CommentListResource, CommentResource
from resources.profile import ProfileResource, MyProfileResource
from resources.friendship import FriendRequestListResource, FriendRequestResource, FriendshipResource
from resources.feed import FeedResource
from resources.category import CategoryResource
from resources.invite import InviteResource

# Load environment variables early
load_dotenv()

# Define base configuration class
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_very_secret_key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = False
    TESTING = False
    # Default to SQLite if DATABASE_URL is not set
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///social_network.db')
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    # S3/R2 Config (Load from environment)
    S3_BUCKET = os.environ.get("S3_BUCKET", "socialnetworkgemma")
    S3_KEY = os.environ.get("S3_KEY")
    S3_SECRET = os.environ.get("S3_SECRET_ACCESS_KEY")
    S3_REGION = os.environ.get("S3_REGION", "auto")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
    DOMAIN_NAME_IMAGES = os.environ.get("DOMAIN_NAME_IMAGES")

    # Other Config
    MODEL_NAME = os.environ.get("MODEL_NAME", "google/gemma-3-4b-it")
    FRONTEND_URL = os.environ.get('FRONTEND_URL', '')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    DEEPINFRA_API_BASE = "https://api.deepinfra.com/v1/openai" # Centralize this

    @staticmethod
    def init_app(app):
        # Placeholder for config-specific initialization if needed later
        pass

# Define development configuration
class DevelopmentConfig(Config):
    DEBUG = True
    # Example: Use a specific dev database if needed
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///social_network_dev.db'

# Define testing configuration
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///:memory:' # Use in-memory SQLite for tests
    WTF_CSRF_ENABLED = False # Disable CSRF forms protection during tests
    SECRET_KEY = 'test-secret-key' # Use a fixed key for tests
    # Disable external services for testing if possible
    S3_BUCKET = None
    OPENAI_API_KEY = None

# Define production configuration
class ProductionConfig(Config):
    # Production specific settings (e.g., force HTTPS, different logging)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') # Get from env

    @staticmethod
    def init_app(app):
        # Call parent init_app if necessary
        # Config.init_app(app)

        # Check for DATABASE_URL when this config is initialized for an app
        database_url = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not database_url:
            raise ValueError("No DATABASE_URL set for production environment")
        
        # Ensure postgres:// is replaced with postgresql://
        if database_url.startswith("postgres://"):
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
            print("INFO: Updated DATABASE_URL prefix for SQLAlchemy in ProductionConfig.")

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig # Default to development
}


# Load blocked categories (can remain outside create_app)
BLOCKED_CATEGORIES = set()
blocked_categories_path = os.path.join(os.path.dirname(__file__), 'blocked_categories.json')
try:
    with open(blocked_categories_path, 'r') as f:
        BLOCKED_CATEGORIES = set(json.load(f))
    print(f"INFO: Loaded {len(BLOCKED_CATEGORIES)} blocked categories from file.")
except FileNotFoundError:
    print(f"WARN: blocked_categories.json not found at {blocked_categories_path}. No categories will be blocked.")
except json.JSONDecodeError:
    print(f"ERROR: Could not decode JSON from {blocked_categories_path}. No categories will be blocked.")


# --- Gemma Classification Class ---
# Moved definition here, depends on loaded categories but not the app instance yet
class GemmaClassification:
    def __init__(self, app_config):
        # Load categories from JSON file or use defaults
        categories_path = os.path.join(os.path.dirname(__file__), 'categories.json')
        try:
            with open(categories_path, 'r') as f:
                self.categories = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"WARN: Could not load categories from {categories_path}: {e}. Using defaults.")
            # Define some sensible defaults if file is missing/invalid
            self.categories = ["Technology", "Travel", "Food", "Art", "Sports", "News", "Lifestyle", "Politics", "Science", "Business", "Entertainment", "Health", "Education", "Environment"]

        # Get config values needed during initialization
        self.model = app_config.get('MODEL_NAME')
        self.openai_api_key = app_config.get('OPENAI_API_KEY')
        self.deepinfra_api_base = app_config.get('DEEPINFRA_API_BASE')

        # Initialize OpenAI client only if API key is available
        if self.openai_api_key and self.deepinfra_api_base:
             self.openai_client = OpenAI(
                api_key=self.openai_api_key,
                base_url=self.deepinfra_api_base,
             )
             print(f"INFO: OpenAI client initialized for model {self.model}")
        else:
             self.openai_client = None
             print("WARN: OpenAI client not initialized (missing API key or base URL).")

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
            return {}  # Return empty dict on error

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


# --- Application Factory ---
def create_app(config_name='default'):
    # Determine configuration type
    config_name = os.getenv('FLASK_CONFIG', config_name) # Allow overriding via environment variable
    app = Flask(__name__, static_folder='../frontend/dist', static_url_path='') # Adjusted static folder path

    # Load configuration from the selected class
    app.config.from_object(config[config_name])
    config[config_name].init_app(app) # Call static init_app if defined

    print(f"INFO: App created with config: {config_name}")
    print(f"INFO: Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

    # Initialize extensions with the app instance
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Initialize Flask-Restful AFTER app is created
    api = Api(app)

    # Custom unauthorized handler for APIs
    @login_manager.unauthorized_handler
    def unauthorized():
        # Return JSON 401 response instead of redirecting
        return jsonify(message="Authentication required."), 401

    # Initialize S3 client if config is present
    if app.config['S3_BUCKET'] and app.config['S3_KEY'] and app.config['S3_SECRET']:
        s3_client = boto3.client('s3',
            endpoint_url=app.config['S3_ENDPOINT_URL'],
            aws_access_key_id=app.config['S3_KEY'],
            aws_secret_access_key=app.config['S3_SECRET'],
            region_name=app.config['S3_REGION'],
        )
        app.config['S3_CLIENT'] = s3_client
        print(f"INFO: S3 Client initialized for bucket {app.config['S3_BUCKET']} in region {app.config['S3_REGION']} (Config: {config_name})")
    else:
        app.config['S3_CLIENT'] = None
        print(f"WARN: S3 credentials not found or disabled for config '{config_name}'. Image upload may be limited.")


    # Initialize GemmaClassification and store in app.config
    # It now takes the already populated app.config
    gemma_classifier = GemmaClassification(app.config)
    app.config['GEMMA_CLASSIFIER'] = gemma_classifier


    # Add API Resources using the 'api' instance initialized above
    api.add_resource(UserRegistration, '/api/v1/register')
    api.add_resource(UserLogin, '/api/v1/login')
    api.add_resource(PostListResource, '/api/v1/posts')
    api.add_resource(PostResource, '/api/v1/posts/<int:post_id>')
    api.add_resource(CommentListResource, '/api/v1/posts/<int:post_id>/comments')
    api.add_resource(CommentResource, '/api/v1/comments/<int:comment_id>')
    api.add_resource(ProfileResource, '/api/v1/profiles/<string:username>')
    api.add_resource(MyProfileResource, '/api/v1/profiles/me')
    api.add_resource(FriendRequestListResource, '/api/v1/friend-requests')
    api.add_resource(FriendRequestResource, '/api/v1/friend-requests/<int:request_id>')
    api.add_resource(FriendshipResource, '/api/v1/friendships/<int:user_id>')
    api.add_resource(FeedResource, '/api/v1/feed')
    api.add_resource(CategoryResource, '/api/v1/categories/<string:category_name>/posts')
    api.add_resource(InviteResource, '/api/v1/invites')

    # --- User Loader for Flask-Login ---
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Method Override (can stay as is) ---
    @app.before_request
    def method_override():
        if request.form and '_method' in request.form:
            method = request.form['_method'].upper()
            if method in ['PUT', 'DELETE', 'PATCH']:
                request.environ['REQUEST_METHOD'] = method

    # --- Routes for serving frontend ---
    @app.route('/')
    @app.route('/<path:path>')
    def serve_react_app(path=None): # Optional path parameter
        # If the path is None (root) or doesn't point to an existing static file...
        if path is None or not os.path.exists(os.path.join(app.static_folder, path)):
             # ... serve the main index.html for client-side routing
             return send_from_directory(app.static_folder, 'index.html')
        else:
             # Otherwise, let Flask serve the static file (e.g., CSS, JS)
             # This part is handled implicitly by Flask if the file exists
             # in static_folder due to static_url_path='' configuration.
             # We might not even need the else clause if static serving works correctly.
             # However, explicitly calling send_from_directory can be clearer.
             return send_from_directory(app.static_folder, path)


    # Add other blueprints or routes here if needed

    return app

# --- Create app instance for running/debugging (outside the factory) ---
# You would typically use a run.py script or flask run command
# which imports and calls create_app()
# For simple execution (e.g., python app.py), you can do this:
if __name__ == '__main__':
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    # Add host='0.0.0.0' to run on network if needed
    app.run(debug=app.config['DEBUG'])


# Remove old app instantiation and config loading that's now inside create_app
# ... (delete the old 'app = Flask(...)' and subsequent app.config lines) ...
# Remove old api = Api(app) line
# Remove old db.init_app(app), login_manager.init_app(app), migrate.init_app(app, db) lines
# Remove old s3_client and openai_client initializations outside the factory
# Remove old GemmaClassification instantiation outside the factory
# Remove old @login_manager.user_loader (moved inside factory)
# Remove old @app.before_request method_override (moved inside factory)
# Remove old @app.route definitions for serving frontend (moved inside factory)