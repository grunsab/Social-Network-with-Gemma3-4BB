from flask import request, jsonify, session
from flask_restful import Resource
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User # Assuming User model is in models.py
from flask_login import login_user, logout_user, login_required
import os

class UserRegistration(Resource):
    def post(self):
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not username or not email or not password:
            return {'message': 'Missing username, email, or password'}, 400

        if User.query.filter_by(username=username).first():
            return {'message': 'Username already exists'}, 409 # Conflict

        if User.query.filter_by(email=email).first():
            return {'message': 'Email already exists'}, 409 # Conflict

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)

        # Set profile picture path based on environment (local vs S3/R2)
        if os.environ.get("S3_BUCKET"): # Assuming S3 indicates cloud storage
             # Use a default placeholder path in the cloud or generate one
             # This might need adjustment based on how S3/R2 paths are structured
             new_user.profile_picture = f"https://{os.environ.get('DOMAIN_NAME_IMAGES')}/default_profile.png" # Example default S3/R2 URL
        else:
             new_user.profile_picture = '/static/images/default_profile.png' # Default local path

        try:
            db.session.add(new_user)
            db.session.commit()
            # Maybe return the created user ID or a success message
            return {'message': 'User created successfully', 'user_id': new_user.id}, 201 # Created
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {e}") # Log the error server-side
            return {'message': 'An error occurred during registration.'}, 500 

class UserLogin(Resource):
    def post(self):
        data = request.get_json()
        identifier = data.get('identifier') # Can be username or email
        password = data.get('password')
        remember = data.get('remember', False) # Optional remember me flag

        if not identifier or not password:
            return {'message': 'Missing username/email or password'}, 400

        # Try finding user by email first, then by username
        user = User.query.filter_by(email=identifier).first()
        if not user:
            user = User.query.filter_by(username=identifier).first()

        if user and check_password_hash(user.password_hash, password):
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

    # Use DELETE method for logout for RESTful convention
    @login_required # Ensure user is logged in to log out
    def delete(self):
        logout_user()
        # Clear any session data if needed, Flask-Login handles the user session part
        session.clear() # Example: clear the whole session
        return {'message': 'Logout successful'}, 200 