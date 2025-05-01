import sys
import os
from werkzeug.security import generate_password_hash
# Remove direct SQLAlchemy imports for engine/sessionmaker
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Add project root to Python path to import app modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import necessary components from the Flask app
from models import User, InviteCode
from extensions import db # Import the db instance
from app import app # Import the Flask app instance

def create_user_in_context(username, password, invite_code_str=None):
    """Creates a user within the Flask app context."""
    invite_code_obj = None
    try:
        # 1. Find and validate the invite code IF provided
        if invite_code_str:
            invite_code_obj = db.session.query(InviteCode).filter_by(code=invite_code_str, is_used=False).first()
            if not invite_code_obj:
                print(f"Error: Invite code '{invite_code_str}' not found or already used.")
                return # No session.close() needed here, context manager handles it

        # 2. Check if username already exists
        existing_user = db.session.query(User).filter_by(username=username).first()
        if existing_user:
            print(f"Error: Username '{username}' already exists.")
            return

        # 3. Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # 4. Create the new user
        new_user = User(
            username=username,
            password_hash=hashed_password,
            used_invite_code=invite_code_str
        )
        db.session.add(new_user)
        # Flush required to get new_user.id *before* linking invite code
        db.session.flush()

        # 5. Mark the invite code as used and link to the new user IF an invite code was used
        if invite_code_obj:
            invite_code_obj.is_used = True
            invite_code_obj.used_by_id = new_user.id
            db.session.add(invite_code_obj)

        # 6. Commit the transaction
        db.session.commit()
        print(f"Successfully created user '{username}'.")

    except IntegrityError as e:
        db.session.rollback()
        print(f"Database integrity error: {e}")
        print("Potential issue: Race condition or unique constraint violation.")
    except Exception as e:
        db.session.rollback()
        print(f"An unexpected error occurred: {e}")
    # No finally/close needed, Flask context manager handles session lifecycle

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python scripts/create_user.py <username> <password> [invite_code]")
        sys.exit(1)

    username_arg = sys.argv[1]
    password_arg = sys.argv[2]
    invite_code_arg = sys.argv[3] if len(sys.argv) == 4 else None

    # Load environment variables BEFORE app context is created
    # This ensures app config picks up any .env settings if the file exists
    from dotenv import load_dotenv
    dotenv_path = os.path.join(project_root, '.env')
    # Only load if .env exists
    if os.path.exists(dotenv_path):
        print("Loading .env file...")
        load_dotenv(dotenv_path=dotenv_path)

    # Run the user creation logic within the Flask application context
    with app.app_context():
        create_user_in_context(username_arg, password_arg, invite_code_arg) 