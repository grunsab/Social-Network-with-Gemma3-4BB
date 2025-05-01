import sys
import os
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Add project root to Python path to import app modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from models import User, InviteCode, Base # Assuming Base is needed for Session
from extensions import db # Import db to potentially use its metadata or session config if needed
from app import app # Import app to get database config

def create_user(username, password, invite_code_str=None):
    """Creates a user in the database using the provided details.
       Optionally uses and marks an invite code as used if provided."""

    # Use the app's database URI configuration
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    engine = create_engine(db_uri)
    Session = sessionmaker(bind=engine)
    session = Session()

    invite_code_obj = None # Initialize invite_code_obj

    try:
        # 1. Find and validate the invite code IF provided
        if invite_code_str:
            invite_code_obj = session.query(InviteCode).filter_by(code=invite_code_str, is_used=False).first()
            if not invite_code_obj:
                print(f"Error: Invite code '{invite_code_str}' not found or already used.")
                session.close() # Close session before returning
                return

        # 2. Check if username already exists
        existing_user = session.query(User).filter_by(username=username).first()
        if existing_user:
            print(f"Error: Username '{username}' already exists.")
            return

        # 3. Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # 4. Create the new user
        new_user = User(
            username=username,
            password_hash=hashed_password,
            # Set used_invite_code to the provided code string, or None if not provided
            used_invite_code=invite_code_str
        )
        session.add(new_user)
        session.flush() # Flush to get the new_user.id

        # 5. Mark the invite code as used and link to the new user IF an invite code was used
        if invite_code_obj:
            invite_code_obj.is_used = True
            invite_code_obj.used_by_id = new_user.id
            session.add(invite_code_obj)

        # 6. Commit the transaction
        session.commit()
        print(f"Successfully created user '{username}'.")

    except IntegrityError as e:
        session.rollback()
        print(f"Database integrity error: {e}")
        print("Potential issue: Race condition or unique constraint violation.")
    except Exception as e:
        session.rollback()
        print(f"An unexpected error occurred: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    # Check for 3 or 4 arguments (script name + user + pass + optional code)
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python scripts/create_user.py <username> <password> [invite_code]")
        sys.exit(1)

    username_arg = sys.argv[1]
    password_arg = sys.argv[2]
    # Set invite_code_arg to None if not provided
    invite_code_arg = sys.argv[3] if len(sys.argv) == 4 else None

    # Load environment variables (needed for DATABASE_URL, SECRET_KEY etc. used by app config)
    from dotenv import load_dotenv
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path) # Load .env from project root

    create_user(username_arg, password_arg, invite_code_arg) 