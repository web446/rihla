"""THE booking code. Every booking in the app goes through create_booking():
the checkout page, the AI agent's Confirm button, and even the seed data.

That way the commission, the seat counting and the safety checks are written
exactly once.
"""
from datetime import date

from extensions import db
from models import Booking, BookingItem, Flight, GuideProfile, Stay
from services.pricing import get_commission_rate, split_commission


class BookingError(Exception):
    """A booking was refused (no seats, guide not approved, bad input...).

    The message is safe to show to the user.
    """


def _load_item(item_type, item_id):
    """Find the flight / stay / guide and return (object, unit price in cents)."""
    if item_type == "flight":
        flight = db.session.get(Flight, item_id)
        if flight is None:
            raise BookingError("That flight does not exist.")
        return flight, flight.price_cents
    if item_type == "stay":
        stay = db.session.get(Stay, item_id)
        if stay is None:
            raise BookingError("That stay does not exist.")
        return stay, stay.price_per_night_cents
    if item_type == "guide":
        guide = db.session.get(GuideProfile, item_id)
        if guide is None or guide.status != "approved":
            raise BookingError("That guide is not available.")
        return guide, guide.price_per_day_cents
    raise BookingError(f"Unknown item type: {item_type}")


def _reserve_seats(flight_id, seats):
    """Take seats from a flight, ONLY if enough are left.

    This is a single UPDATE with a condition, done by the database:
        UPDATE flights SET seats_available = seats_available - :seats
        WHERE id = :id AND seats_available >= :seats
    If two people book the last seat at the same moment, only one UPDATE can
    match, so the flight can never be overbooked. rowcount tells us if it worked.
    """
    result = db.session.execute(
        db.update(Flight)
        .where(Flight.id == flight_id, Flight.seats_available >= seats)
        .values(seats_available=Flight.seats_available - seats)
    )
    if result.rowcount != 1:
        raise BookingError("Sorry, there are not enough seats left on that flight.")


def _check_trip_rules(loaded, start_date, end_date, allow_past):
    """Business rules for a whole trip. `loaded` = [(type, object, quantity, unit)].

    These live HERE (not in the page) so the checkout page and the AI agent
    are held to exactly the same rules.
    """
    if not allow_past and start_date <= date.today():
        raise BookingError("Trips must start after today.")
    types = [item_type for item_type, *_ in loaded]
    if len(types) != len(set(types)):
        raise BookingError("A trip can have one flight, one stay and one guide.")
    if len({target.country_id for _, target, _, _ in loaded}) > 1:
        raise BookingError("Everything in one trip must be in the same country.")

    nights = (end_date - start_date).days
    for item_type, target, quantity, _ in loaded:
        if item_type == "flight":
            if (target.depart_date, target.return_date) != (start_date, end_date):
                raise BookingError("The trip dates must match the flight dates.")
            if quantity > 9:
                raise BookingError("You can book up to 9 seats at a time.")
        elif item_type == "stay" and quantity > max(nights, 1):
            raise BookingError(f"This trip only has {nights} night(s).")
        elif item_type == "guide" and quantity > nights + 1:
            raise BookingError(f"This trip only has {nights + 1} day(s) for a guide.")


def _load_and_check(items, start_date, end_date, allow_past=False):
    """Load every item and apply all the trip rules. Changes NOTHING.

    Returns [(type, object, quantity, unit price in cents)].
    """
    if not items:
        raise BookingError("Your trip is empty.")
    if not isinstance(start_date, date) or not isinstance(end_date, date) or end_date < start_date:
        raise BookingError("Please choose valid trip dates.")
    loaded = []
    for spec in items:
        item_type = spec.get("type")
        quantity = int(spec.get("quantity", 1))
        if quantity < 1 or quantity > 60:
            raise BookingError("Quantities must be between 1 and 60.")
        target, unit_cents = _load_item(item_type, int(spec.get("id")))
        loaded.append((item_type, target, quantity, unit_cents))
    _check_trip_rules(loaded, start_date, end_date, allow_past)
    return loaded


def preview_booking(items, start_date, end_date):
    """Check a trip and price it WITHOUT booking anything.

    Used by the AI agent to show the summary the traveler must confirm.
    Runs the exact same rules as create_booking(), plus a seat check
    (create_booking re-checks seats atomically when the user confirms).
    """
    try:
        loaded = _load_and_check(items, start_date, end_date)
    except (ValueError, TypeError) as error:
        raise BookingError("Some booking details were invalid.") from error
    lines = []
    for item_type, target, quantity, unit_cents in loaded:
        if item_type == "flight" and target.seats_available < quantity:
            raise BookingError(f"Only {target.seats_available} seat(s) left on that flight.")
        lines.append({"type": item_type, "id": target.id, "quantity": quantity,
                      "unit_cents": unit_cents, "total_cents": unit_cents * quantity})
    return {"lines": lines, "total_cents": sum(line["total_cents"] for line in lines),
            "country": loaded[0][1].country}


def create_booking(traveler, items, start_date, end_date, source="web", allow_past=False):
    """Create one confirmed booking (a trip) and return it.

    traveler   : the logged-in User (always taken from the session, never from a form)
    items      : list of dicts, e.g.
                 [{"type": "flight", "id": 3, "quantity": 2},   # 2 seats
                  {"type": "stay",   "id": 7, "quantity": 5},   # 5 nights
                  {"type": "guide",  "id": 2, "quantity": 2}]   # 2 days
    source     : "web" (checkout page) or "agent" (AI travel agent)
    allow_past : only the seed data uses True, to create trips that already happened

    Either everything is saved, or nothing is (on any error we roll back).
    """
    if traveler is None or traveler.role != "traveler":
        raise BookingError("Only travelers can book trips.")
    if not items:
        raise BookingError("Your trip is empty.")
    if not isinstance(start_date, date) or not isinstance(end_date, date) or end_date < start_date:
        raise BookingError("Please choose valid trip dates.")

    rate = get_commission_rate()
    # traveler_id (not traveler=...) so a refused booking is never attached to the user object
    booking = Booking(traveler_id=traveler.id, start_date=start_date, end_date=end_date,
                      commission_rate=rate, status="confirmed", source=source,
                      total_cents=0, commission_cents=0, provider_cents=0)

    try:
        # 1. Load everything and check the rules BEFORE changing anything.
        loaded = _load_and_check(items, start_date, end_date, allow_past)

        # 2. Save: reserve seats, price every line, add up the totals.
        db.session.add(booking)  # part of the current transaction until commit()
        for item_type, target, quantity, unit_cents in loaded:
            if item_type == "flight":
                _reserve_seats(target.id, quantity)

            # The commission is calculated per line, then added up.
            line_total = unit_cents * quantity
            commission, provider = split_commission(line_total, rate)

            booking.items.append(BookingItem(
                item_type=item_type,
                flight=target if item_type == "flight" else None,
                stay=target if item_type == "stay" else None,
                guide=target if item_type == "guide" else None,
                quantity=quantity,
                unit_price_cents=unit_cents,
                line_total_cents=line_total,
                commission_cents=commission,
                provider_cents=provider,
            ))
            booking.total_cents += line_total
            booking.commission_cents += commission
            booking.provider_cents += provider

        db.session.commit()
        return booking
    except (BookingError, ValueError, TypeError) as error:
        db.session.rollback()  # undo the seat reservation and everything else
        if isinstance(error, BookingError):
            raise
        raise BookingError("Some booking details were invalid.") from error


def cancel_booking(booking, user):
    """Cancel a booking owned by `user` and give the flight seats back."""
    if booking is None or booking.traveler_id != user.id:
        # Same message for "not found" and "not yours": we don't reveal other users' bookings.
        raise BookingError("Booking not found.")
    if booking.status != "confirmed":
        raise BookingError("This booking is already cancelled.")
    if booking.start_date <= date.today():
        raise BookingError("Trips that have already started cannot be cancelled.")

    for item in booking.items:
        if item.item_type == "flight":
            item.flight.seats_available += item.quantity  # restore the seats
    booking.status = "cancelled"
    db.session.commit()
    return booking
