from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

# Define limiter instance globally but initialize it later with the app
limiter = Limiter(
    key_func=get_remote_address,
    # You might want to adjust default limits or remove them
    # if you prefer defining all limits where they are used.
    default_limits=["200 per day", "50 per hour"] 
)

@event.listens_for(Engine, "connect")
def _enable_sqlite_fk_constraints(dbapi_connection, connection_record):
    # Only enable SQLite foreign key constraints when using SQLite
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()