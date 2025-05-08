import sys
import os

# Add project root to Python path to import app modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from models import User, Ampersound
from extensions import db
from app import create_app

def make_user_ampersounds_public(username):
    """Finds a user by username and sets all their ampersounds to public."""
    user = User.query.filter_by(username=username).first()

    if not user:
        print(f"Error: User '{username}' not found.")
        return

    ampersounds_to_update = Ampersound.query.filter_by(user_id=user.id).all()

    if not ampersounds_to_update:
        print(f"User '{username}' has no ampersounds.")
        return

    updated_count = 0
    for ampersound in ampersounds_to_update:
        if ampersound.privacy != 'public':
            ampersound.privacy = 'public'
            updated_count += 1
    
    if updated_count > 0:
        try:
            db.session.commit()
            print(f"Successfully updated {updated_count} ampersound(s) to public for user '{username}'.")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating ampersounds for user '{username}': {e}")
    else:
        print(f"All ampersounds for user '{username}' are already public.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/make_ampersounds_public.py <username>")
        sys.exit(1)

    username_arg = sys.argv[1]

    # Load environment variables if .env file exists
    from dotenv import load_dotenv
    dotenv_path = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path):
        print("Loading .env file...")
        load_dotenv(dotenv_path=dotenv_path)

    app = create_app()

    with app.app_context():
        make_user_ampersounds_public(username_arg)
