from flask import request, jsonify, session, current_app
from flask_restful import Resource
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, InviteCode # Import InviteCode
from flask_login import login_user, logout_user, login_required
import os

class UserRegistration(Resource):
    def post(self):
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        invite_code_str = data.get('invite_code') # Get invite code from request

        invite_code_obj = None # To store the valid InviteCode object if found

        # --- Invite Code Validation ---
        # Make invite code mandatory only if INVITE_ONLY is True
        if current_app.config.get('INVITE_ONLY', True):
            if not invite_code_str:
                return {'message': 'Invite code is required for registration'}, 400

            invite_code_obj = InviteCode.query.filter_by(code=invite_code_str).first()
            if not invite_code_obj or invite_code_obj.is_used:
                return {'message': 'Invalid or used invite code'}, 400 # Bad Request
        # If INVITE_ONLY is False, we can proceed without an invite code (invite_code_obj will be None)

        if not username or not email or not password:
            return {'message': 'Missing username, email, or password'}, 400

        if User.query.filter_by(username=username).first():
            return {'message': 'Username already exists'}, 409 # Conflict

        if User.query.filter_by(email=email).first():
            return {'message': 'Email already exists'}, 409 # Conflict

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(
            username=username, 
            email=email, 
            password_hash=hashed_password,
            # Link user to inviter if applicable
            invited_by_user_id=invite_code_obj.issuer_id if invite_code_obj else None
        )

        # Set profile picture path based on environment (local vs S3/R2)
        if os.environ.get("S3_BUCKET"): # Assuming S3 indicates cloud storage
             # Use a default placeholder path in the cloud or generate one
             # This might need adjustment based on how S3/R2 paths are structured
             new_user.profile_picture = f"https://{os.environ.get('DOMAIN_NAME_IMAGES')}/default_profile.png" # Example default S3/R2 URL
        else:
             new_user.profile_picture = '/static/images/default_profile.png' # Default local path

        try:
            print(f"DEBUG: Attempting to add User: {new_user.username}, Invite Issuer: {invite_code_obj.issuer_id if invite_code_obj else 'None'}")
            db.session.add(new_user)
            # Mark invite code as used AFTER adding user, before commit
            if invite_code_obj:
                # Wait until user is added and has an ID before associating
                db.session.flush() # Ensure new_user gets an ID
                print(f"DEBUG: Marking invite code {invite_code_obj.code} as used by user ID {new_user.id}.") # Debug print
                invite_code_obj.is_used = True 
                invite_code_obj.used_by_id = new_user.id # Set the foreign key on InviteCode
                db.session.add(invite_code_obj) 
            
            print("DEBUG: Attempting db.session.commit()") # Debug print
            db.session.commit()
            print("DEBUG: db.session.commit() successful.") # Debug print
            # Maybe return the created user ID or a success message
            return {'message': 'User created successfully', 'user_id': new_user.id}, 201 # Created
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {e}") # Log the error server-side
            return {'message': 'An error occurred during registration.'}, 500 

class UserLogin(Resource):
    decorators = [current_app.config['limiter'].limit("20 per day")] # Apply rate limit

    def post(self):
        data = request.get_json()
        identifier = data.get('identifier') # Can be username or email
        password = data.get('password')
        remember = data.get('remember', False) # Optional remember me flag

        if not identifier or not password:
            return {'message': 'Missing username/email or password'}, 400

        # Try finding user by email first, then by username
        # Explicitly select only needed columns to avoid issues with model changes
        user_data = User.query.with_entities(User.id, User.password_hash, User.username, User.email, User.profile_picture).filter_by(email=identifier).first()
        if not user_data:
            user_data = User.query.with_entities(User.id, User.password_hash, User.username, User.email, User.profile_picture).filter_by(username=identifier).first()

        # Reconstruct a minimal user-like object or check directly
        if user_data and check_password_hash(user_data.password_hash, password):
            # Need the actual User object to pass to flask_login.login_user
            # Re-query for the full object now that we know the user is valid
            user = User.query.get(user_data.id)
            if not user: # Should not happen, but defensive check
                 return {'message': 'Login failed after verification'}, 500
                 
            login_user(user, remember=remember)
            # Return user info upon successful login
            return {
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'profile_picture': user.profile_picture
                    # Add other relevant user fields
                }
            }, 200
        else:
            return {'message': 'Invalid credentials'}, 401 # Unauthorized

class UserLogout(Resource):
    @login_required
    def post(self): # Typically logout is a POST to prevent CSRF if it changes state
        logout_user()
        return {'message': 'Successfully logged out'}, 200 