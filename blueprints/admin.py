"""Admin-only pages. Every route has @role_required("admin")."""
from flask import Blueprint, render_template

from security import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@role_required("admin")
def dashboard():
    # Placeholder until Step 6 (admin dashboard).
    return render_template("partials/placeholder.html", title="Admin dashboard",
                           message="Stats, guide approvals and content management come in Step 6.")
