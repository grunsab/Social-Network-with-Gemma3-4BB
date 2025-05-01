import sys
import os
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import SQLAlchemyError

# Add project root to Python path to import app modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import necessary components from the Flask app
from models import User
from extensions import db # Import the db instance
from app import app # Import the Flask app instance

def update_password_in_context(username, new_password):
    """Updates a user's password within the Flask app context."""
    try:
        # 1. Find the user by username
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return

        # 2. Hash the new password
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')

        # 3. Update the user's password hash
        user.password_hash = hashed_password
        db.session.add(user) # Add the modified user object to the session

        # 4. Commit the transaction
        db.session.commit()
        print(f"Successfully updated password for user '{username}'.")

    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Database error during password update: {e}")
    except Exception as e:
        db.session.rollback()
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/update_password.py <username> <new_password>")
        sys.exit(1)

    username_arg = sys.argv[1]
    new_password_arg = sys.argv[2]

    # Optional: Load .env file if needed for app configuration
    # from dotenv import load_dotenv
    # dotenv_path = os.path.join(project_root, '.env')
    # if os.path.exists(dotenv_path):
    #     print("Loading .env file...")
    #     load_dotenv(dotenv_path=dotenv_path)

    # Run the password update logic within the Flask application context
    with app.app_context():
        update_password_in_context(username_arg, new_password_arg) 