import pytest
from app import create_app, db as _db # Import your app factory and db instance
from models import User, Post, Comment, Ampersound # Import models
from models import UserType, PostPrivacy, CommentVisibility # Import enums
from werkzeug.security import generate_password_hash
from flask_login import login_user, logout_user

@pytest.fixture(scope='session')
def app():
    """Session-wide test Flask application."""
    # Ensure FLASK_CONFIG is set to 'testing' or your test config name
    _app = create_app(config_name='testing') 

    # Establish an application context before running the tests.
    with _app.app_context():
        yield _app

@pytest.fixture()
def client(app):
    """A test client for the app."""
    with app.test_client() as client:
        yield client

@pytest.fixture(scope='function') # Use 'function' scope for clean DB per test
def db_session(app):
    """Creates a new database session for a test with setup and teardown."""
    with app.app_context(): # Ensure operations are within app context
        _db.create_all() # Create all tables
        
        yield _db.session # Provide the session for use in tests
        
        _db.session.remove() # Close the session
        _db.drop_all() # Drop all tables after the test

# --- Model Creation Fixture Factories (as functions for reusability) ---

@pytest.fixture
def create_user(db_session):
    def _create_user(username="testuser", email="test@example.com", password="password123", user_type=UserType.USER, commit=True):
        user = User(
            username=username, 
            email=email, 
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            user_type=user_type
        )
        db_session.add(user)
        if commit:
            try:
                db_session.commit()
            except Exception as e:
                db_session.rollback()
                raise e
        return user
    return _create_user

@pytest.fixture
def create_post(db_session, create_user):
    def _create_post(user_id=None, content="Test Post Content", privacy=PostPrivacy.PUBLIC, commit=True):
        if user_id is None:
            # Create a default user if none provided
            default_user = create_user(username='postauthor', email='postauthor@example.com', commit=False) # Don't commit yet if part of larger transaction
            db_session.add(default_user)
            db_session.flush() # Get ID for default_user
            user_id = default_user.id

        post = Post(user_id=user_id, content=content, privacy=privacy)
        db_session.add(post)
        if commit:
            try:
                db_session.commit()
            except Exception as e:
                db_session.rollback()
                raise e
        return post
    return _create_post

@pytest.fixture
def create_comment(db_session, create_user, create_post):
    def _create_comment(user_id=None, post_id=None, content="Test Comment Content", visibility=CommentVisibility.PUBLIC, commit=True):
        if user_id is None:
            default_user = create_user(username='commenter', email='commenter@example.com', commit=False)
            db_session.add(default_user)
            db_session.flush()
            user_id = default_user.id
        
        if post_id is None:
            # Create a default post if none provided
            default_post_author = create_user(username='commentpostauthor', email='commentpostauthor@example.com', commit=False)
            db_session.add(default_post_author)
            db_session.flush()
            default_post = create_post(user_id=default_post_author.id, content="Parent post for comment", commit=False)
            db_session.add(default_post)
            db_session.flush()
            post_id = default_post.id

        comment = Comment(user_id=user_id, post_id=post_id, content=content, visibility=visibility)
        db_session.add(comment)
        if commit:
            try:
                db_session.commit()
            except Exception as e:
                db_session.rollback()
                raise e
        return comment
    return _create_comment

@pytest.fixture
def create_ampersound(db_session, create_user):
    def _create_ampersound(user_id=None, name="testsound", file_path="path/to/test.mp3", privacy="public", commit=True):
        if user_id is None:
            default_user = create_user(username='ampsoundowner', email='ampsoundowner@example.com', commit=False)
            db_session.add(default_user)
            db_session.flush()
            user_id = default_user.id
        
        ampersound = Ampersound(user_id=user_id, name=name, file_path=file_path, privacy=privacy)
        db_session.add(ampersound)
        if commit:
            try:
                db_session.commit()
            except Exception as e:
                db_session.rollback()
                raise e
        return ampersound
    return _create_ampersound

# --- Auth Fixtures ---

@pytest.fixture
def regular_user_auth_data(client, create_user, db_session, app):
    user = create_user(username='testregular', email='regular@example.com', password='password')
    client.post('/api/v1/login', json={
        'identifier': 'regular@example.com',
        'password': 'password'
    })
    yield {'headers': {}, 'user': user}
    # Teardown: Use a new, simple request context for logout_user()
    with app.test_request_context('/'): 
        logout_user()

@pytest.fixture
def admin_user_auth_data(client, create_user, db_session, app):
    admin_user = create_user(username='testadmin', email='admin@example.com', password='password', user_type=UserType.ADMIN)
    client.post('/api/v1/login', json={
        'identifier': 'admin@example.com',
        'password': 'password'
    })
    yield {'headers': {}, 'user': admin_user}
    # Teardown: Use a new, simple request context for logout_user()
    with app.test_request_context('/'):
        logout_user()

# Note: The auth fixtures above assume a POST to /api/v1/login for session setup.
# If your login mechanism is different (e.g., token-based, or login_user directly sets a cookie 
# the client picks up without a POST), these might need adjustment.
# The key is that subsequent requests from `client` in the test are authenticated as the user. 