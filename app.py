"""Rihla: entry point of the Flask application.

Run (inside the activated .venv):
    flask --app app init-db          -> (re)create the database with sample data
    flask --app app db-summary       -> print how many rows each table has
    flask --app app run --debug      -> http://127.0.0.1:5000/
On Render:  gunicorn app:app
"""
import os

import click
from flask import Flask, jsonify, render_template, request, url_for

from config import Config
from extensions import db
from security import check_csrf, csrf_token, load_current_user
from services.pricing import format_money


def create_app():
    """Build and configure the Flask app (the "application factory" pattern)."""
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)          # connect SQLAlchemy to this app
    import models  # noqa: F401  (registers the tables with SQLAlchemy)

    # {{ 12345|money }} in a template shows "$123.45"
    app.jinja_env.filters["money"] = format_money
    # {{ csrf_token() }} can be used in every template (hidden field in forms)
    app.jinja_env.globals["csrf_token"] = csrf_token

    def asset(filename):
        """URL of a static file + ?v=<last modified time>. When the file changes, the
        URL changes, so browsers can't keep using an old cached copy."""
        path = os.path.join(app.static_folder, filename)
        version = int(os.path.getmtime(path)) if os.path.exists(path) else 0
        return url_for("static", filename=filename, v=version)

    app.jinja_env.globals["asset"] = asset

    # Runs before every request, in this order:
    app.before_request(load_current_user)   # g.user = logged-in user or None
    app.before_request(check_csrf)          # refuse forms without a valid token

    # Blueprints = groups of routes (Chapter 9)
    from blueprints.admin import admin_bp
    from blueprints.auth import auth_bp
    from blueprints.guide import guide_bp
    from blueprints.public import public_bp
    from blueprints.traveler import traveler_bp
    for blueprint in (public_bp, auth_bp, traveler_bp, guide_bp, admin_bp):
        app.register_blueprint(blueprint)

    register_error_pages(app)
    register_cli_commands(app)
    return app


def register_error_pages(app):
    """Friendly pages instead of the default white error screens."""
    messages = {
        400: ("Something went wrong", "That request was not valid."),
        403: ("Passport control", "Your account does not have access to this page."),
        404: ("Off the map", "We couldn't find that page."),
    }
    for code, (title, default_text) in messages.items():
        def handler(error, code=code, title=title, default_text=default_text):
            text = getattr(error, "description", None) if code == 400 else default_text
            if request.path.startswith("/api/"):   # /api/estimate (calculator) answers in JSON
                return jsonify({"error": text or default_text}), code
            return render_template("error.html", code=code, title=title, text=text or default_text), code
        app.register_error_handler(code, handler)


def register_cli_commands(app):
    """Extra terminal commands: flask --app app <command>."""

    @app.cli.command("init-db")
    def init_db():
        """Delete all tables, create them again and insert the sample data."""
        from sqlalchemy import MetaData

        from seed import TEST_ACCOUNTS, seed_database
        # Drop EVERY table found in the database file, even tables of features that
        # were removed from models.py (db.drop_all() only knows the current models).
        existing = MetaData()
        existing.reflect(bind=db.engine)
        existing.drop_all(bind=db.engine)
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
