"""Objects shared by the whole app.

The SQLAlchemy object is created here, WITHOUT an app, and connected to the
app later in app.py with db.init_app(app). Keeping it in its own file lets
models.py, services/ and app.py all import the same `db` without importing
each other in a circle.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
