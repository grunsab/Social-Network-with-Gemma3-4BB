import os
import sys
import argparse

# Adjust the Python path to include the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from app import create_app, db
from models import User, Post, PostPrivacy # Assuming PostPrivacy is an enum in models.py

def set_user_posts_to_friends_only(username):
    """
    Finds a user by username and sets all their posts to friends-only.
    """
    # Determine the config to use. Default to 'development' if FLASK_CONFIG is not set.
    # This is important if your app behaves differently based on config (e.g., different DBs)
    # For a script like this, 'production' or a dedicated 'script' config might be appropriate
    # if you want it to always run against the production DB when FLASK_CONFIG=production.
    # Or, you might always want it to run with a 'development' like config if it's a dev tool.
    # Let's default to 'production' for safety if FLASK_CONFIG is set, otherwise 'default'.
    config_name = os.getenv('FLASK_CONFIG', 'default')
    if config_name == 'default' and 'FLASK_CONFIG' in os.environ: # e.g. FLASK_CONFIG=""
        config_name = 'development'


    app = create_app(config_name)

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return

        posts_updated_count = 0
        for post in user.posts:
            if post.privacy != PostPrivacy.FRIENDS:
                post.privacy = PostPrivacy.FRIENDS
                posts_updated_count += 1
        
        if posts_updated_count > 0:
            try:
                db.session.commit()
                print(f"Successfully updated {posts_updated_count} posts for user '{username}' to friends-only.")
            except Exception as e:
                db.session.rollback()
                print(f"Error committing changes to the database: {e}")
        else:
            print(f"No posts needed updating for user '{username}' or user has no posts.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Set all posts of a specified user to friends-only.")
    parser.add_argument('username', type=str, help='The username of the user whose posts will be updated.')
    
    args = parser.parse_args()
    
    set_user_posts_to_friends_only(args.username) 