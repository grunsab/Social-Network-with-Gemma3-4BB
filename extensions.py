from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

@event.listens_for(Engine, "connect")
def _enable_sqlite_fk_constraints(dbapi_connection, connection_record):
    # Only enable SQLite foreign key constraints when using SQLite
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()