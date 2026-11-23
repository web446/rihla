"""Guide-only pages: dashboard (status, bookings, rating, earnings) and profile."""
from datetime import date

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from extensions import db
from models import Booking, BookingItem, Country, Review
from security import role_required
from validators import validate_guide_profile

guide_bp = Blueprint("guide", __name__, url_prefix="/guide")


@guide_bp.route("/dashboard")
@role_required("guide")
def dashboard():
    profile = g.user.guide_profile
    today = date.today()

    # Every booked day with this guide, newest trips first (JOIN booking_items -> bookings)
    items = db.session.execute(
        db.select(BookingItem).join(Booking)
        .where(BookingItem.guide_id == profile.id)
        .order_by(Booking.start_date.desc())
    ).scalars().all()
    confirmed = [i for i in items if i.booking.status == "confirmed"]

    # Earnings = the guide's share (provider_cents), i.e. the price minus the platform commission.
    # SUM is done by the database; a CASE splits finished trips from upcoming ones.
    earned, upcoming = db.session.execute(
        db.select(
            func.coalesce(func.sum(db.case((Booking.end_date < today, BookingItem.provider_cents), else_=0)), 0),
            func.coalesce(func.sum(db.case((Booking.end_date >= today, BookingItem.provider_cents), else_=0)), 0),
        ).join(Booking).where(BookingItem.guide_id == profile.id, Booking.status == "confirmed")
    ).one()

    reviews = db.session.execute(
        db.select(Review).where(Review.guide_id == profile.id).order_by(Review.created_at.desc())
    ).scalars().all()

    return render_template(
        "guide/dashboard.html", profile=profile, items=items, today=today,
        stats={
            "earned": earned, "upcoming": upcoming,
            "trips": len(confirmed),
            "days": sum(i.quantity for i in confirmed),
            "rating": profile.average_rating(), "reviews": len(reviews),
        },
        reviews=reviews,
    )


@guide_bp.route("/profile", methods=["GET", "POST"])
@role_required("guide")
def profile():
    """Edit country, languages, bio and price. A rejected guide who edits is sent back for review."""
    profile = g.user.guide_profile
    countries = db.session.execute(db.select(Country).order_by(Country.name)).scalars().all()
    if request.method == "GET":
        values = {"country_id": profile.country_id, "languages": profile.languages, "bio": profile.bio,
                  "price": f"{profile.price_per_day_cents / 100:.0f}"}
        return render_template("guide/profile.html", errors={}, values=values, countries=countries, profile=profile)

    errors, cleaned = validate_guide_profile(request.form, {c.id for c in countries})
    if errors:
        return render_template("guide/profile.html", errors=errors, values=cleaned,
                               countries=countries, profile=profile), 400

    profile.country_id = cleaned["country_id"]
    profile.languages = cleaned["languages"]
    profile.bio = cleaned["bio"]
    profile.price_per_day_cents = cleaned["price_per_day_cents"]
    if profile.status == "rejected":
        profile.status = "pending"
        flash("Profile updated and sent to our team again for approval.", "success")
    else:
        flash("Profile updated.", "success")
    db.session.commit()
    return redirect(url_for("guide.dashboard"))
