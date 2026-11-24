"""Objects shared by the whole app.

The SQLAlchemy object is created here, WITHOUT an app, and connected to the
app later in app.py with db.init_app(app). Keeping it in its own file lets
models.py, services/ and app.py all import the same `db` without importing
each other in a circle.
"""
import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignores FOREIGN KEY rules unless this is switched on for every
    connection. With it on, the database itself refuses e.g. deleting a flight
    that is still referenced by a booking. (PostgreSQL always checks them.)"""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
