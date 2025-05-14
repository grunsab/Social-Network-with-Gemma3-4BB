import sys
import os
import argparse

# Add project root to Python path to import app modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, project_root)

from sqlalchemy import func

from models import User, Ampersound, AmpersoundStatus
from extensions import db
from app import create_app

def approve_ampersound_script(username, ampersound_name):
    """Finds an ampersound by username and ampersound name, then approves it."""
    app = create_app()
    with app.app_context():
        user = User.query.filter(func.lower(User.username) == func.lower(username)).first()

        if not user:
            print(f"Error: User '{username}' not found.")
            return

        # Ampersound names are stored in lowercase and without special chars
        # Assuming ampersound_name input might not be cleaned,
        # but the database stores it cleaned. For direct matching,
        # we might need to rely on the input being the exact stored name.
        # Or, if the creation process cleans it, the input here should also be cleaned
        # or we query more flexibly if needed.
        # For now, assume ampersound_name is the exact name stored.
        ampersound = Ampersound.query.filter(
            Ampersound.user_id == user.id,
            func.lower(Ampersound.name) == func.lower(ampersound_name)
        ).first()

        if not ampersound:
            print(f"Error: Ampersound '{ampersound_name}' for user '{username}' not found.")
            return

        if ampersound.status == AmpersoundStatus.APPROVED:
            print(f"Ampersound '&{user.username}.{ampersound.name}' is already approved.")
            return

        if ampersound.status == AmpersoundStatus.REJECTED:
            print(f"Warning: Ampersound '&{user.username}.{ampersound.name}' was previously REJECTED. Approving it now.")

        ampersound.status = AmpersoundStatus.APPROVED
        
        try:
            db.session.commit()
            print(f"Successfully approved ampersound '&{user.username}.{ampersound.name}'. Status: {ampersound.status.value}")
        except Exception as e:
            db.session.rollback()
            print(f"Error approving ampersound '&{user.username}.{ampersound.name}': {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Approve an ampersound for a user.')
    parser.add_argument('username', type=str, help='The username of the ampersound creator.')
    parser.add_argument('ampersound_name', type=str, help='The name of the ampersound.')

    args = parser.parse_args()

    # Validate that username and ampersound_name are provided
    if not args.username or not args.ampersound_name:
        parser.print_help()
        sys.exit(1)
        
    approve_ampersound_script(args.username, args.ampersound_name) 