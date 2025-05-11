import sys
import os
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

# Add project root to Python path to import app modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import necessary components from the Flask app
from models import User, InviteCode
from extensions import db
from app import create_app

def create_user_in_context(username, password, email, invite_code_str=None):
    """Creates or updates a user within the Flask app context."""
    try:
        existing_user = db.session.query(User).filter_by(username=username).first()
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        if existing_user:
            print(f"User '{username}' already exists. Updating password and email if different.")
            existing_user.password_hash = hashed_password
            if existing_user.email != email:
                # Check if the new email is already taken by another user
                other_user_with_email = db.session.query(User).filter(User.email == email, User.id != existing_user.id).first()
                if other_user_with_email:
                    print(f"Error: New email '{email}' is already in use by another user '{other_user_with_email.username}'. Rolling back.")
                    db.session.rollback()
                    return
                print(f"Updating email for '{username}' from '{existing_user.email}' to '{email}'.")
                existing_user.email = email
            
            print(f"Password and email for user '{username}' updated (if changed).")
        else:
            print(f"Creating new user '{username}' with email '{email}'.")
            
            # Validate email uniqueness for new user
            if db.session.query(User).filter_by(email=email).first():
                print(f"Error: Email '{email}' already exists for a new user. Cannot create '{username}'.")
                return

            invite_code_obj = None
            if invite_code_str:
                invite_code_obj = db.session.query(InviteCode).filter_by(code=invite_code_str, is_used=False).first()
                if not invite_code_obj:
                    print(f"Error: Invite code '{invite_code_str}' not found or already used. Cannot create new user '{username}'.")
                    return

            new_user = User(
                username=username,
                email=email,
                password_hash=hashed_password,
                invited_by_user_id=invite_code_obj.issuer_id if invite_code_obj else None
            )

            if os.environ.get("S3_BUCKET"):
                 new_user.profile_picture = f"https://{os.environ.get('DOMAIN_NAME_IMAGES')}/default_profile.png"
            else:
                 new_user.profile_picture = '/static/images/default_profile.png'

            db.session.add(new_user)
            db.session.flush() 

            if invite_code_obj:
                print(f"Marking invite code {invite_code_obj.code} as used by new user ID {new_user.id}.")
                invite_code_obj.is_used = True
                invite_code_obj.used_by_id = new_user.id
                db.session.add(invite_code_obj)
            
            print(f"Successfully created user '{username}'.")
        
        db.session.commit()

    except IntegrityError as e:
        db.session.rollback()
        print(f"Database integrity error: {e}")
        print("This might be a race condition or a unique constraint violation not caught by pre-checks (e.g. email for existing user if not handled above).")
    except Exception as e:
        db.session.rollback()
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print("Usage: python scripts/create_user.py <username> <password> <email> [invite_code]")
        sys.exit(1)

    username_arg = sys.argv[1]
    password_arg = sys.argv[2]
    email_arg = sys.argv[3]
    invite_code_arg = sys.argv[4] if len(sys.argv) == 5 else None

    from dotenv import load_dotenv
    dotenv_path = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path):
        print("Loading .env file...")
        load_dotenv(dotenv_path=dotenv_path)

    app = create_app()

    with app.app_context():
        create_user_in_context(username_arg, password_arg, email_arg, invite_code_arg)