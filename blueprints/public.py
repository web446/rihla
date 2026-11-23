"""Pages anyone can see (no login needed)."""
from flask import Blueprint, render_template

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    # Step 3 replaces this with the full homepage.
    return render_template("public/home.html")
