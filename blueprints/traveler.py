"""Traveler-only pages. Every route has @role_required("traveler")."""
from flask import Blueprint, render_template

from security import role_required

traveler_bp = Blueprint("traveler", __name__, url_prefix="/me")


@traveler_bp.route("/trips")
@role_required("traveler")
def trips():
    # Placeholder until Step 4 (booking system).
    return render_template("partials/placeholder.html", title="My Trips",
                           message="Your booked trips will appear here (Step 4).")
