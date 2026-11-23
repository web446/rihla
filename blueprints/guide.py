"""Guide-only pages. Every route has @role_required("guide")."""
from flask import Blueprint, g, render_template

from security import role_required

guide_bp = Blueprint("guide", __name__, url_prefix="/guide")


@guide_bp.route("/dashboard")
@role_required("guide")
def dashboard():
    # Placeholder until Step 5 (bookings, ratings, earnings).
    profile = g.user.guide_profile
    status = profile.status if profile else "missing"
    return render_template("partials/placeholder.html", title="Guide dashboard",
                           message=f"Your profile status: {status}. Bookings and earnings come in Step 5.")
