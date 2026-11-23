"""Admin-only pages. Every route has @role_required("admin")."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import GuideProfile
from security import role_required
from services import search

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@role_required("admin")
def dashboard():
    # Placeholder until Step 6 (admin dashboard).
    pending = db.session.execute(
        db.select(db.func.count(GuideProfile.id)).where(GuideProfile.status == "pending")).scalar()
    return render_template("partials/placeholder.html", title="Admin dashboard",
                           message=f"{pending} guide(s) waiting for approval. Stats and content management come in Step 6.",
                           link=(url_for("admin.guides"), "Review guides"))


@admin_bp.route("/guides")
@role_required("admin")
def guides():
    status = request.args.get("status", "pending")
    if status not in ("pending", "approved", "rejected"):
        status = "pending"
    profiles = db.session.execute(
        db.select(GuideProfile).where(GuideProfile.status == status).order_by(GuideProfile.id.desc())
    ).scalars().all()
    counts = dict(db.session.execute(
        db.select(GuideProfile.status, db.func.count()).group_by(GuideProfile.status)).all())
    ratings = {g.id: (avg, n) for g, avg, n in search.guides_with_ratings()}
    return render_template("admin/guides.html", profiles=profiles, status=status, counts=counts, ratings=ratings)


@admin_bp.route("/guides/<int:guide_id>/status", methods=["POST"])
@role_required("admin")
def set_guide_status(guide_id):
    """Approve or reject a guide (POST + CSRF token, like every change)."""
    profile = db.session.get(GuideProfile, guide_id)
    new_status = request.form.get("status")
    if profile is None or new_status not in ("approved", "rejected", "pending"):
        flash("Invalid request.", "danger")
        return redirect(url_for("admin.guides"))
    profile.status = new_status
    db.session.commit()
    verb = {"approved": "approved ✅ and now visible to travelers", "rejected": "rejected",
            "pending": "moved back to pending"}[new_status]
    flash(f"{profile.user.full_name} was {verb}.", "success" if new_status == "approved" else "info")
    return redirect(url_for("admin.guides", status=request.form.get("back", "pending")))
