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


def create_booking(traveler, items, start_date, end_date, source="web"):
    """Create one confirmed booking (a trip) and return it.

    traveler   : the logged-in User (always taken from the session, never from a form)
    items      : list of dicts, e.g.
                 [{"type": "flight", "id": 3, "quantity": 2},   # 2 seats
                  {"type": "stay",   "id": 7, "quantity": 5},   # 5 nights
                  {"type": "guide",  "id": 2, "quantity": 2}]   # 2 days
    source     : "web" (checkout page) or "agent" (AI travel agent)

    Either everything is saved, or nothing is (on any error we roll back).
    """
    if traveler is None or traveler.role != "traveler":
        raise BookingError("Only travelers can book trips.")
    if not items:
        raise BookingError("Your trip is empty.")
    if not isinstance(start_date, date) or not isinstance(end_date, date) or end_date < start_date:
        raise BookingError("Please choose valid trip dates.")

    rate = get_commission_rate()
    booking = Booking(traveler=traveler, start_date=start_date, end_date=end_date,
                      commission_rate=rate, status="confirmed", source=source,
                      total_cents=0, commission_cents=0, provider_cents=0)

    try:
        db.session.add(booking)  # part of the current transaction until commit()
        for spec in items:
            item_type = spec.get("type")
            item_id = int(spec.get("id"))
            quantity = int(spec.get("quantity", 1))
            if quantity < 1 or quantity > 60:
                raise BookingError("Quantities must be between 1 and 60.")

            target, unit_cents = _load_item(item_type, item_id)
            if item_type == "flight":
                _reserve_seats(item_id, quantity)

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
