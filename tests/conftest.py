import pytest
from app import create_app, db

@pytest.fixture(scope='module')
def test_app():
    app = create_app('testing')  # Assuming you have a 'testing' config
    app_context = app.app_context()
    app_context.push()
    db.create_all()

    yield app  # Provide the app object to the tests

    db.session.remove()
    db.drop_all()
    app_context.pop()

@pytest.fixture(scope='module')
def test_client(test_app):
    return test_app.test_client() 