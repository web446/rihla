"""App settings, read from environment variables (Chapter 9: "secrets and
addresses live in the environment, never in the code").

python-dotenv copies the lines of the .env file into the environment, so
os.environ.get(...) finds them. If .env does not exist, the defaults below
are used, which is fine for local development.
"""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def database_uri():
    # If DATABASE_URL is set (e.g. a PostgreSQL address) it is used; otherwise SQLite.
    # "sqlite:///rihla.db" is created inside the instance/ folder by Flask-SQLAlchemy.
    # On Render we also use SQLite: the build command runs "flask --app app init-db".
    url = os.environ.get("DATABASE_URL") or "sqlite:///rihla.db"
    return url.replace("postgres://", "postgresql://", 1)


class Config:
    # Signs the session cookie so users cannot edit it. The fallback is for
    # local development only; a real deployment must set SECRET_KEY.
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me"

    SQLALCHEMY_DATABASE_URI = database_uri()
