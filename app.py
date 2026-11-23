"""Rihla: entry point of the Flask application.

Run (inside the activated .venv):
    flask --app app init-db          -> (re)create the database with sample data
    flask --app app db-summary       -> print how many rows each table has
    flask --app app run --debug      -> http://127.0.0.1:5000/
On Render:  gunicorn app:app
"""
import click
from flask import Flask

from config import Config
from extensions import db
from services.pricing import format_money


def create_app():
    """Build and configure the Flask app (the "application factory" pattern)."""
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)          # connect SQLAlchemy to this app
    import models  # noqa: F401  (registers the tables with SQLAlchemy)

    # {{ 12345|money }} in a template shows "$123.45"
    app.jinja_env.filters["money"] = format_money

    @app.route("/")
    def home():
        # Temporary page for Step 1; replaced by the real homepage in Step 3.
        return "<h1>Rihla is running.</h1><p>Database step done. Pages come next.</p>"

    register_cli_commands(app)
    return app


def register_cli_commands(app):
    """Extra terminal commands: flask --app app <command>."""

    @app.cli.command("init-db")
    def init_db():
        """Delete all tables, create them again and insert the sample data."""
        from seed import TEST_ACCOUNTS, seed_database
        db.drop_all()
        db.create_all()       # turns every class in models.py into a table
        seed_database()
        click.echo("Database created and filled with sample data.")
        click.echo("Test logins:")
        for role, (email, password) in TEST_ACCOUNTS.items():
            click.echo(f"  {role:9} {email:22} {password}")

    @app.cli.command("db-summary")
    def db_summary():
        """Show the number of rows in each table."""
        for table in db.metadata.sorted_tables:
            count = db.session.execute(db.select(db.func.count()).select_from(table)).scalar()
            click.echo(f"  {table.name:20} {count}")


app = create_app()
