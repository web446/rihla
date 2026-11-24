"""Booking proposals: the safety step between the AI and the database.

The agent's create_booking / cancel_booking tools never touch bookings.
They only save a BookingProposal and show a summary card. The booking is
made when the LOGGED-IN USER clicks "Confirm" (or types "confirm"), and it
goes through services/booking.py: the same code as the checkout page.
"""
import json
from datetime import date, datetime, timedelta

from extensions import db
from models import Booking, BookingProposal
from services.booking import BookingError, cancel_booking, create_booking
from services.pricing import format_money

PROPOSAL_LIFETIME = timedelta(minutes=15)


class ProposalError(Exception):
    pass


def save_proposal(user, conversation_id, action, payload, total_cents):
    """Store a new pending proposal. Older pending ones in this chat expire,
    so "confirm" always means the LATEST summary the user saw."""
    db.session.execute(
        db.update(BookingProposal)
        .where(BookingProposal.user_id == user.id, BookingProposal.conversation_id == conversation_id,
               BookingProposal.status == "pending")
        .values(status="expired")
    )
    proposal = BookingProposal(user_id=user.id, conversation_id=conversation_id, action=action,
                               payload_json=json.dumps(payload), total_cents=total_cents)
    db.session.add(proposal)
    db.session.commit()
    return proposal


def latest_pending(user, conversation_id):
    return db.session.execute(
        db.select(BookingProposal)
        .where(BookingProposal.user_id == user.id, BookingProposal.conversation_id == conversation_id,
               BookingProposal.status == "pending")
        .order_by(BookingProposal.id.desc())
    ).scalars().first()


def _get_own_pending(proposal_id, user):
    proposal = db.session.get(BookingProposal, proposal_id)
    if proposal is None or proposal.user_id != user.id:   # never another user's proposal
        raise ProposalError("I couldn't find that booking summary.")
    if proposal.status != "pending":
        raise ProposalError("That summary was already used or replaced. Ask me to prepare it again.")
    if datetime.now() - proposal.created_at > PROPOSAL_LIFETIME:
        proposal.status = "expired"
        db.session.commit()
        raise ProposalError("That summary expired (prices and seats may have changed). Ask me to prepare it again.")
    return proposal


def confirm(proposal_id, user):
    """The user said yes: run the REAL booking or cancellation. Returns (text, cards)."""
    proposal = _get_own_pending(proposal_id, user)
    payload = json.loads(proposal.payload_json)
    try:
        if proposal.action == "create":
            booking = create_booking(user, payload["items"], date.fromisoformat(payload["start"]),
                                     date.fromisoformat(payload["end"]), source="agent")
            text = (f"✅ Booked! Trip #{booking.id} to {booking.country.name} is confirmed "
                    f"({booking.start_date:%d %b} → {booking.end_date:%d %b %Y}). You'll find it in My Trips.")
        else:
            booking = cancel_booking(db.session.get(Booking, payload["booking_id"]), user)
            text = f"Trip #{booking.id} is cancelled. Any flight seats were released."
    except BookingError as error:
        proposal.status = "expired"
        db.session.commit()
        raise ProposalError(f"I couldn't complete that: {error}") from error

    proposal.status = "confirmed"
    db.session.commit()
    return text, [booking_card(booking)]


def decline(proposal_id, user):
    proposal = _get_own_pending(proposal_id, user)
    proposal.status = "expired"
    db.session.commit()
    return "No problem, nothing was booked or changed. What would you like to adjust?"


def booking_card(booking):
    return {
        "type": "booking", "booking_id": booking.id,
        "country": booking.country.name if booking.country else "",
        "dates": f"{booking.start_date:%d %b} → {booking.end_date:%d %b %Y}",
        "total": format_money(booking.total_cents), "status": booking.status,
        "items": [item.title for item in booking.items],
    }
