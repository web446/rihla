"""Traveler-only pages: trip basket, simulated checkout, My Trips, cancel.

Every route has @role_required("traveler"), and every booking is looked up
together with g.user.id, so a traveler can only ever see or change their
OWN bookings.
"""
from datetime import date

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from extensions import db
from models import Booking
from security import is_safe_next_url, role_required
from services import basket
from services.booking import BookingError, cancel_booking, create_booking

traveler_bp = Blueprint("traveler", __name__, url_prefix="/me")

# Allowed quantity for each item type: (smallest, largest, what it counts)
QUANTITY_LIMITS = {"flight": (1, 9, "seats"), "stay": (1, 30, "nights"), "guide": (1, 14, "days")}


def _read_quantity(item_type, text):
    low, high, unit = QUANTITY_LIMITS[item_type]
    try:
        value = int(text)
    except (TypeError, ValueError):
        return None, f"Please enter a number of {unit}."
    if not low <= value <= high:
        return None, f"Choose between {low} and {high} {unit}."
    return value, None


# ---------------------------------------------------------------------------
# Basket
# ---------------------------------------------------------------------------
@traveler_bp.route("/basket/add", methods=["POST"])
@role_required("traveler")
def basket_add():
    item_type = request.form.get("item_type")
    back = request.form.get("next", "")
    back = back if is_safe_next_url(back) else url_for("public.home")
    if item_type not in basket.MODELS:
        flash("That item can't be booked.", "danger")
        return redirect(back)

    quantity, error = _read_quantity(item_type, request.form.get("quantity"))
    try:
        obj = db.session.get(basket.MODELS[item_type], int(request.form.get("item_id", "")))
    except ValueError:
        obj = None
    if obj is None or (item_type == "guide" and obj.status != "approved"):
        error = "That item is no longer available."
    elif item_type == "flight" and (obj.depart_date <= date.today() or obj.seats_available < (quantity or 1)):
        error = f"Only {obj.seats_available} seat(s) left on that flight."
    if error:
        flash(error, "danger")
        return redirect(back)

    if basket.add(item_type, obj, quantity):
        flash("Your basket had items from another country, so we started a new trip.", "warning")
    flash("Added to your trip.", "success")
    return redirect(url_for("traveler.basket_view"))


@traveler_bp.route("/basket")
@role_required("traveler")
def basket_view():
    return render_template("traveler/basket.html", trip=basket.details(), today=date.today())


@traveler_bp.route("/basket/update", methods=["POST"])
@role_required("traveler")
def basket_update():
    """Change quantities and (when there is no flight) the trip dates."""
    trip = basket.details()
    if trip is None:
        return redirect(url_for("traveler.basket_view"))
    for item_type, (obj, _) in trip["items"].items():
        quantity, error = _read_quantity(item_type, request.form.get(f"qty_{item_type}"))
        if error:
            flash(error, "danger")
            return redirect(url_for("traveler.basket_view"))
        basket.add(item_type, obj, quantity)
    if not trip["dates_fixed"]:
        basket.set_dates(request.form.get("start", ""), request.form.get("end", ""))
    flash("Trip updated.", "success")
    return redirect(url_for("traveler.basket_view"))


@traveler_bp.route("/basket/remove/<item_type>", methods=["POST"])
@role_required("traveler")
def basket_remove(item_type):
    if item_type in basket.MODELS:
        basket.remove(item_type)
    return redirect(url_for("traveler.basket_view"))


# ---------------------------------------------------------------------------
# Simulated checkout
# ---------------------------------------------------------------------------
@traveler_bp.route("/checkout", methods=["GET", "POST"])
@role_required("traveler")
def checkout():
    trip = basket.details()
    if trip is None:
        flash("Your trip basket is empty.", "info")
        return redirect(url_for("public.countries"))
    if not trip["start"] or not trip["end"]:
        flash("Please choose your trip dates first.", "warning")
        return redirect(url_for("traveler.basket_view"))

    if request.method == "GET":
        return render_template("traveler/checkout.html", trip=trip)

    # The "payment": no card, no real money. The traveler just confirms.
    if request.form.get("confirm_simulated") != "yes":
        flash("Please tick the box to confirm this simulated payment.", "warning")
        return render_template("traveler/checkout.html", trip=trip), 400

    try:
        # THE shared booking function: same commission, seats and rules as the AI agent.
        booking = create_booking(g.user, trip["booking_items"], trip["start"], trip["end"], source="web")
    except BookingError as error:
        flash(str(error), "danger")
        return redirect(url_for("traveler.basket_view"))

    basket.clear()
    flash(f"Booked! Your trip to {trip['country'].name} is confirmed. Bon voyage!", "success")
    return redirect(url_for("traveler.trips", new=booking.id))


# ---------------------------------------------------------------------------
# My Trips
# ---------------------------------------------------------------------------
@traveler_bp.route("/trips")
@role_required("traveler")
def trips():
    bookings = db.session.execute(
        db.select(Booking).where(Booking.traveler_id == g.user.id)   # ONLY this user's bookings
        .order_by(Booking.start_date)
    ).scalars().all()
    today = date.today()
    groups = {
        "upcoming": [b for b in bookings if b.status == "confirmed" and b.start_date > today],
        "past": [b for b in bookings if b.status == "confirmed" and b.start_date <= today][::-1],
        "cancelled": [b for b in bookings if b.status == "cancelled"],
    }
    return render_template("traveler/trips.html", groups=groups, today=today,
                           new_id=request.args.get("new", type=int))


@traveler_bp.route("/trips/<int:booking_id>/cancel", methods=["POST"])
@role_required("traveler")
def cancel(booking_id):
    try:
        booking = cancel_booking(db.session.get(Booking, booking_id), g.user)
        flash(f"Trip #{booking.id} was cancelled. Any flight seats were released.", "info")
    except BookingError as error:
        flash(str(error), "danger")
    return redirect(url_for("traveler.trips"))
