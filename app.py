import os
import json
import uuid
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_login import login_required, current_user
from flask_restful import Api
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, func, case, desc, union_all, and_
from sqlalchemy.orm import joinedload, undefer
from dotenv import load_dotenv
import boto3
from openai import OpenAI
import mimetypes
from werkzeug.utils import secure_filename
import re # Import regular expression module

# Import extensions and models AFTER defining configurations
from extensions import db, login_manager, migrate
# Import models here if they don't depend on the app instance directly at import time
# If models.py imports 'app', this needs further adjustment.
# Corrected imports: Use InviteCode instead of Invite.
# Removed Profile, Friendship, and Category as they don't exist as distinct models.
from models import User, Post, Comment, FriendRequest, InviteCode, UserInterest, PostPrivacy, Ampersound

# Import Resources AFTER defining configurations and extensions
from resources.auth import UserRegistration, UserLogin, UserLogout
from resources.post import PostListResource, PostResource
from resources.comment import CommentListResource, CommentResource
from resources.profile import ProfileResource, MyProfileResource, profile_data_fields
from resources.friendship import FriendRequestListResource, FriendRequestResource, FriendshipResource
from resources.feed import FeedResource
from resources.category import CategoryResource
from resources.invite import InviteResource
from resources.report import ReportResource

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
                return {}

            # Basic validation
            if not isinstance(self.category_scores, dict):
                print(f"ERROR: Classification result is not a dictionary: {type(self.category_scores)}")
                return {}
            
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
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print(f"!!! DEBUG: create_app FUNCTION CALLED    !!!")
    print(f"!!! DEBUG: config_name = {config_name}        !!!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    app = Flask(__name__, static_folder='frontend/dist', static_url_path='/app_assets') # Corrected static folder path

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
        # Return a JSON response, which is typical for APIs
        # Flask-RESTful might also handle this, but explicit is good.
        response = jsonify(message="Authentication required.")
        response.status_code = 401
        return response

    # Initialize S3 client if config is present
    s3_client = None
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
    api.add_resource(UserLogout, '/api/v1/logout')
    api.add_resource(PostListResource, '/api/v1/posts')
    api.add_resource(PostResource, '/api/v1/posts/<int:post_id>')
    api.add_resource(CommentListResource, '/api/v1/posts/<int:post_id>/comments')
    api.add_resource(CommentResource, '/api/v1/comments/<int:comment_id>')
    api.add_resource(ProfileResource, '/api/v1/profiles/<string:username>')
    api.add_resource(FriendRequestListResource, '/api/v1/friend-requests')
    api.add_resource(FriendRequestResource, '/api/v1/friend-requests/<int:request_id>')
    api.add_resource(FriendshipResource, '/api/v1/friendships/<int:user_id>')
    api.add_resource(FeedResource, '/api/v1/feed')
    api.add_resource(CategoryResource, '/api/v1/categories/<string:category_name>/posts')
    api.add_resource(InviteResource, '/api/v1/invites', '/api/v1/invites/<string:code>')
    api.add_resource(ReportResource, '/api/v1/reports')

    # --- Manually add routes for MyProfileResource --- 
    # Instantiate the resource once (though it's stateless here)
    my_profile_view = MyProfileResource() 

    @app.route('/api/v1/profiles/me', methods=['GET'])
    @login_required
    def get_my_profile():
        # Manually call the resource's get method
        # Note: marshal_with won't apply automatically, but resource method returns dict.
        # Return data with default 200 status.
        response_data = my_profile_view.get()
        return jsonify(response_data), 200

    @app.route('/api/v1/profiles/me', methods=['PATCH'])
    @login_required
    def patch_my_profile():
        # Manually call the resource's patch method
        # Note: marshal_with won't apply automatically, resource method returns dict.
        # Return data with default 200 status.
        response_data = my_profile_view.patch()
        return jsonify(response_data), 200

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
        # Ensure os is available (it's imported at the top of app.py)
        # Ensure send_from_directory is available (imported from flask at the top)
        
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"--- DEBUG: SERVE_REACT_APP CALLED WITH PATH: {path} ---")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # 'app' is the Flask instance from the create_app scope
        effective_static_folder = app.static_folder
        print(f"app.static_folder (resolved by Flask): {effective_static_folder}")

        index_html_full_path = os.path.join(effective_static_folder, 'index.html')
        print(f"Expected index.html full path: {index_html_full_path}")
        print(f"Does index.html exist at that path according to os.path.exists? {os.path.exists(index_html_full_path)}")

        # Case 1: Root path requested (path is None, e.g., GET /)
        if path is None:
            print(f"Path is None (root '/'). Attempting to serve index.html.")
            if not os.path.exists(index_html_full_path):
                print(f"CRITICAL ERROR: index.html not found at {index_html_full_path} when serving root.")
                return jsonify(message="Application critical error: Main page not found."), 500 # Or 404
            return send_from_directory(effective_static_folder, 'index.html')

        # Case 2: A specific path is requested (e.g., /favicon.ico, /assets/main.js, or a client-side route like /profile)
        specific_file_full_path = os.path.join(effective_static_folder, path)
        print(f"Specific path requested: '{path}'. Checking for file: {specific_file_full_path}")
        
        # Check if the specific file exists and is not a directory
        if os.path.exists(specific_file_full_path) and not os.path.isdir(specific_file_full_path):
            print(f"File '{path}' found in static folder. Attempting to serve it directly.")
            return send_from_directory(effective_static_folder, path)
        else:
            # If the specific file/asset is not found, or if the path is for client-side routing, serve index.html.
            print(f"File '{path}' not found or is a directory in static folder. Fallback: attempting to serve index.html.")
            if not os.path.exists(index_html_full_path):
                 print(f"CRITICAL ERROR: index.html not found at {index_html_full_path} when serving as fallback for path '{path}'.")
                 return jsonify(message=f"Application not found (index.html missing for path: {path})"), 404
            return send_from_directory(effective_static_folder, 'index.html')

    # --- Ampersounds Routes ---

    @app.route('/api/v1/ampersounds', methods=['POST'])
    @login_required
    def create_ampersound():
        if 'audio_file' not in request.files:
            return jsonify({"message": "No audio file part"}), 400
        file = request.files['audio_file']
        name = request.form.get('name')
        privacy = request.form.get('privacy', 'public').lower()

        if privacy not in ['public', 'friends']:
            privacy = 'public' # Default to public if invalid value is provided

        if not name:
            return jsonify({"message": "Ampersound name is required"}), 400
        
        # Validate name (simple validation for now: alphanumeric, no spaces)
        # The name will be used in URLs and as a tag, so keep it simple.
        clean_name = secure_filename(name).lower() # basic sanitization
        if not clean_name or clean_name != name.lower() or '&' in clean_name or ' ' in clean_name:
            return jsonify({"message": "Invalid Ampersound name. Use alphanumeric characters without spaces or '&'."}), 400

        if file.filename == '':
            return jsonify({"message": "No selected file"}), 400

        # Check if an ampersound with this name already exists for the user
        existing_ampersound = Ampersound.query.filter_by(user_id=current_user.id, name=clean_name).first()
        if existing_ampersound:
            return jsonify({"message": f"You already have an Ampersound named '{clean_name}'."}), 409 # Conflict

        if file and s3_client:
            filename = secure_filename(file.filename)
            # Try to guess extension, default to .mp3 or .wav if not found
            content_type = file.mimetype
            extension = mimetypes.guess_extension(content_type)
            if not extension:
                # Fallback for common audio types if mimetypes fails or is too generic (e.g. application/octet-stream)
                if 'webm' in content_type:
                    extension = '.webm'
                elif 'wav' in content_type:
                    extension = '.wav'
                elif 'ogg' in content_type:
                    extension = '.ogg'
                else:
                    extension = '.mp3' # Default fallback
            
            s3_filename = f"ampersounds/{current_user.id}/{clean_name}{extension}"
            s3_bucket = app.config['S3_BUCKET']

            try:
                s3_client.upload_fileobj(
                    file,
                    s3_bucket,
                    s3_filename,
                    ExtraArgs={'ContentType': content_type}
                )
                file_url = f"{app.config.get('DOMAIN_NAME_IMAGES', '')}/{s3_filename}" # Assuming DOMAIN_NAME_IMAGES is the base URL for S3 content
                if app.config.get('S3_ENDPOINT_URL') and not app.config.get('DOMAIN_NAME_IMAGES'):
                    # If using a custom endpoint (like MinIO/R2) and no specific domain for images,
                    # construct URL based on bucket and endpoint.
                    # This might need adjustment based on S3 provider's URL structure.
                    file_url = f"{app.config['S3_ENDPOINT_URL']}/{s3_bucket}/{s3_filename}"

                ampersound = Ampersound(
                    user_id=current_user.id,
                    name=clean_name,
                    file_path=s3_filename, # Store S3 key/path
                    privacy=privacy
                )
                db.session.add(ampersound)
                db.session.commit()
                return jsonify({"message": "Ampersound created successfully!", "name": clean_name, "url": file_url, "ampersound_id": ampersound.id}), 201
            except Exception as e:
                app.logger.error(f"Error uploading ampersound to S3: {e}")
                return jsonify({"message": "Error uploading file to S3."}), 500
        elif not s3_client:
            return jsonify({"message": "File storage (S3) is not configured on the server."}), 500
        else:
            return jsonify({"message": "Invalid file."}), 400

    @app.route('/ampersounds/<string:username>/<string:sound_name>', methods=['GET'])
    def get_ampersound(username, sound_name):
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({"message": "User not found"}), 404

        clean_sound_name = secure_filename(sound_name).lower()
        ampersound = Ampersound.query.filter_by(user_id=user.id, name=clean_sound_name).first()
        if not ampersound:
            return jsonify({"message": "Ampersound not found"}), 404

        # Privacy check
        can_view = False
        if ampersound.privacy == 'public':
            can_view = True
        elif ampersound.privacy == 'friends':
            if current_user.is_authenticated:
                if ampersound.user_id == current_user.id or current_user.is_friend(ampersound.user):
                    can_view = True
        
        if not can_view:
            return jsonify({"message": "You do not have permission to view this Ampersound"}), 403

        # Increment play_count
        try:
            ampersound.play_count = (Ampersound.play_count or 0) + 1 # Ensure play_count is not None before incrementing
            db.session.add(ampersound) # Add to session, or it might already be there
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error incrementing play_count for ampersound {ampersound.id}: {e}")
            # Decide if this should be a critical error or just logged. For now, we log and continue.

        s3_client = app.config.get('S3_CLIENT') # Get S3 client from app config
        s3_bucket = app.config.get('S3_BUCKET')
        domain_name = app.config.get('DOMAIN_NAME_IMAGES')
        s3_endpoint_url = app.config.get('S3_ENDPOINT_URL')
        s3_key = ampersound.file_path

        try:
            if domain_name: 
                file_url = f"{domain_name}/{s3_key}"
            elif s3_endpoint_url: 
                file_url = f"{s3_endpoint_url}/{s3_bucket}/{s3_key}"
            else: 
                s3_region = app.config.get('S3_REGION', 'us-east-1') 
                if s3_region == 'auto': 
                    return jsonify({"message": "Cannot construct S3 URL with 'auto' region for AWS S3."}), 500
                file_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{s3_key}"
            
            return jsonify({
                "name": ampersound.name, 
                "url": file_url, 
                "user": user.username, 
                "play_count": ampersound.play_count,
                "privacy": ampersound.privacy # Include privacy in response
            }), 200
        except Exception as e:
            app.logger.error(f"Error generating Ampersound URL for {ampersound.id}: {e}")
            return jsonify({"message": "Error retrieving Ampersound URL."}), 500

    @app.route('/api/v1/ampersounds/my_sounds', methods=['GET'])
    @login_required
    def list_my_ampersounds():
        user_ampersounds = Ampersound.query.filter_by(user_id=current_user.id).order_by(Ampersound.timestamp.desc()).all()
        
        s3_client = app.config.get('S3_CLIENT') # Get S3 client from app config
        s3_bucket = app.config.get('S3_BUCKET')
        domain_name_images = app.config.get('DOMAIN_NAME_IMAGES')
        s3_endpoint_url = app.config.get('S3_ENDPOINT_URL')
        s3_region = app.config.get('S3_REGION', 'us-east-1')

        results = []
        for ampersound in user_ampersounds:
            file_url = None
            if s3_client and s3_bucket:
                s3_key = ampersound.file_path
                try:
                    if domain_name_images:
                        file_url = f"{domain_name_images}/{s3_key}"
                    elif s3_endpoint_url:
                        file_url = f"{s3_endpoint_url}/{s3_bucket}/{s3_key}"
                    else:
                        if s3_region == 'auto': # Should not happen if properly configured for AWS S3
                            app.logger.warn(f"Cannot construct S3 URL for {s3_key} with 'auto' region for AWS S3.")
                            file_url = None # Or some placeholder/error indicator
                        else:
                            file_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{s3_key}"
                except Exception as e:
                    app.logger.error(f"Error generating URL for ampersound {ampersound.id}: {e}")
            
            results.append({
                'id': ampersound.id,
                'name': ampersound.name,
                'file_path': ampersound.file_path, # Or use the generated file_url
                'url': file_url, # The generated playable URL
                'timestamp': ampersound.timestamp.isoformat(),
                'privacy': ampersound.privacy # Include privacy setting
            })
        
        return jsonify(results), 200

    @app.route('/api/v1/ampersounds/all', methods=['GET'])
    def list_all_ampersounds():
        base_query = (
            Ampersound.query
            .join(User, User.id == Ampersound.user_id)
            .options(joinedload(Ampersound.user))
        )

        if current_user.is_authenticated:
            friend_ids = current_user.get_friend_ids()
            # Show public ampersounds OR friends-only ampersounds from friends OR ampersounds owned by the current user
            base_query = base_query.filter(
                or_(
                    Ampersound.privacy == 'public',
                    and_(Ampersound.privacy == 'friends', Ampersound.user_id.in_(friend_ids)),
                    Ampersound.user_id == current_user.id # Always show user's own ampersounds
                )
            )
        else:
            # For anonymous users, only show public ampersounds
            base_query = base_query.filter(Ampersound.privacy == 'public')

        all_ampersounds = (
            base_query
            .order_by(Ampersound.play_count.desc(), Ampersound.timestamp.desc())
            .limit(50)
            .all()
        )

        s3_client = app.config.get('S3_CLIENT')
        s3_bucket = app.config.get('S3_BUCKET')
        domain_name_images = app.config.get('DOMAIN_NAME_IMAGES')
        s3_endpoint_url = app.config.get('S3_ENDPOINT_URL')
        s3_region = app.config.get('S3_REGION', 'us-east-1')

        results = []
        for ampersound in all_ampersounds:
            file_url = None
            if s3_client and s3_bucket:
                s3_key = ampersound.file_path
                try:
                    if domain_name_images:
                        file_url = f"{domain_name_images}/{s3_key}"
                    elif s3_endpoint_url:
                        file_url = f"{s3_endpoint_url}/{s3_bucket}/{s3_key}"
                    else:
                        if s3_region == 'auto':
                            app.logger.warn(f"Cannot construct S3 URL for {s3_key} with 'auto' region for AWS S3.")
                        else:
                            file_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{s3_key}"
                except Exception as e:
                    app.logger.error(f"Error generating URL for ampersound {ampersound.id}: {e}")
            
            results.append({
                'id': ampersound.id,
                'name': ampersound.name,
                'user': {
                    'id': ampersound.user.id,
                    'username': ampersound.user.username
                },
                'url': file_url,
                'timestamp': ampersound.timestamp.isoformat(),
                'play_count': ampersound.play_count, # Include play_count in response
                'privacy': ampersound.privacy # Include privacy in response
            })
        
        return jsonify(results), 200

    @app.route('/api/v1/ampersounds/<int:sound_id>', methods=['DELETE'])
    @login_required
    def delete_ampersound(sound_id):
        ampersound = Ampersound.query.get(sound_id)

        if not ampersound:
            return jsonify({"message": "Ampersound not found"}), 404

        # Verify ownership
        if ampersound.user_id != current_user.id:
            return jsonify({"message": "You do not have permission to delete this Ampersound"}), 403 # Forbidden

        s3_client = app.config.get('S3_CLIENT')
        s3_bucket = app.config.get('S3_BUCKET')
        s3_key_to_delete = ampersound.file_path

        try:
            # Delete from DB first
            db.session.delete(ampersound)
            db.session.commit()

            # Then attempt to delete from S3
            if s3_client and s3_bucket and s3_key_to_delete:
                try:
                    s3_client.delete_object(Bucket=s3_bucket, Key=s3_key_to_delete)
                    app.logger.info(f"Successfully deleted S3 object: {s3_key_to_delete}")
                except Exception as s3_error:
                    # Log S3 deletion error but don't fail the request if DB delete succeeded
                    app.logger.error(f"Error deleting S3 object {s3_key_to_delete} for deleted ampersound {sound_id}: {s3_error}")
            
            return jsonify({"message": "Ampersound deleted successfully"}), 200
        
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error deleting ampersound {sound_id} from database: {e}")
            return jsonify({"message": "Failed to delete Ampersound"}), 500

    @app.route('/api/v1/ampersounds/search', methods=['GET'])
    @login_required 
    def search_ampersounds():
        query_term = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)

        if not query_term:
            return jsonify([]) 

        results = []
        username_part = None
        soundname_part = None
        base_query = Ampersound.query.join(User, User.id == Ampersound.user_id)

        if '.' in query_term:
            parts = query_term.split('.', 1)
            username_part = parts[0]
            soundname_part = parts[1]
            username_pattern = f"{username_part}%"
            soundname_pattern = f"{soundname_part}%"
            base_query = base_query.filter(
                func.lower(User.username).ilike(username_pattern),
                func.lower(Ampersound.name).ilike(soundname_pattern)
            )
        else:
            soundname_pattern = f"{query_term}%"
            base_query = base_query.filter(func.lower(Ampersound.name).ilike(soundname_pattern))

        # Apply privacy filtering
        if current_user.is_authenticated:
            friend_ids = current_user.get_friend_ids()
            base_query = base_query.filter(
                or_(
                    Ampersound.privacy == 'public',
                    and_(Ampersound.privacy == 'friends', Ampersound.user_id.in_(friend_ids)),
                    Ampersound.user_id == current_user.id
                )
            )
        else:
            # Anonymous users only see public results in search too
            base_query = base_query.filter(Ampersound.privacy == 'public')

        ampersounds_query = (
            base_query
            .options(joinedload(Ampersound.user))
            .order_by(User.username, Ampersound.name) # Consider if order_by needs adjustment post-privacy
            .limit(limit)
        )

        found_ampersounds = ampersounds_query.all()
        
        # Get S3 config for URL generation
        s3_client = app.config.get('S3_CLIENT')
        s3_bucket = app.config.get('S3_BUCKET')
        domain_name_images = app.config.get('DOMAIN_NAME_IMAGES')
        s3_endpoint_url = app.config.get('S3_ENDPOINT_URL')
        s3_region = app.config.get('S3_REGION', 'us-east-1')

        for sound in found_ampersounds:
            tag = f"&{sound.user.username}.{sound.name}"
            file_url = None # Generate URL
            if s3_client and s3_bucket:
                s3_key = sound.file_path
                try:
                    if domain_name_images:
                        file_url = f"{domain_name_images}/{s3_key}"
                    elif s3_endpoint_url:
                        file_url = f"{s3_endpoint_url}/{s3_bucket}/{s3_key}"
                    else:
                        if s3_region == 'auto':
                            app.logger.warn(f"Cannot construct S3 URL for {s3_key} with 'auto' region for AWS S3.")
                        else:
                            file_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{s3_key}"
                except Exception as e:
                    app.logger.error(f"Error generating URL for search result ampersound {sound.id}: {e}")

            results.append({
                "id": sound.id, # Include ID for potential future use
                "tag": tag,
                "owner": sound.user.username,
                "name": sound.name,
                "url": file_url, # Add the generated URL
                "privacy": sound.privacy # Include privacy setting
            })

        return jsonify(results)

    return app

# Create app instance for Gunicorn/WSGI server
# FLASK_CONFIG should be 'production' in the Heroku environment.
# If FLASK_CONFIG is not set, it defaults to 'production' here.
application = create_app(os.getenv('FLASK_CONFIG', 'production'))

if __name__ == '__main__':
    # When running directly (e.g., python app.py), use 'default' (DevelopmentConfig)
    # if FLASK_CONFIG is not set. This allows easy local development.
    # The 'PORT' env var is used by Heroku, so it's good to include.
    # Host '0.0.0.0' is also good practice for containerized environments.
    config_name_for_run = os.getenv('FLASK_CONFIG') or 'default'
    app_for_run = create_app(config_name_for_run)
    # Heroku dynamically assigns a port, so use PORT environment variable.
    # Default to 5000 for local development if PORT is not set.
    port = int(os.environ.get("PORT", 5000))
    app_for_run.run(debug=app_for_run.config['DEBUG'], host='0.0.0.0', port=port)


# Remove old app instantiation and config loading that's now inside create_app
# ... (delete the old 'app = Flask(...)' and subsequent app.config lines) ...
# Remove old api = Api(app) line
# Remove old db.init_app(app), login_manager.init_app(app), migrate.init_app(app, db) lines
# Remove old s3_client and openai_client initializations outside the factory
# Remove old GemmaClassification instantiation outside the factory
# Remove old @login_manager.user_loader (moved inside factory)
# Remove old @app.before_request method_override (moved inside factory)
# Remove old @app.route definitions for serving frontend (moved inside factory)