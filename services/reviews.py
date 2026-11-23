"""Who may review a guide, and saving the review.

Rule: only a traveler who REALLY booked the guide, on a confirmed trip that
has ENDED, can leave one review for that booking. The guide's star rating
is then simply AVG(reviews.rating) (see GuideProfile.average_rating).
"""
from datetime import date

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import BookingItem, Review


class ReviewError(Exception):
    """A review was refused; the message is safe to show to the user."""


def review_problem(item, user):
    """Return why `user` can't review this booking line, or None if they can."""
    if item is None or item.booking.traveler_id != user.id:
        return "Booking not found."             # also hides other people's bookings
    if item.item_type != "guide":
        return "Only guides can be reviewed."
    if item.booking.status != "confirmed":
        return "Cancelled trips can't be reviewed."
    if item.booking.end_date > date.today():
        return "You can review your guide once the trip has ended."
    if item.review is not None:
        return "You already reviewed this guide for this trip."
    return None


def can_review(item, user):
    return review_problem(item, user) is None


def create_review(item_id, user, rating, comment):
    item = db.session.get(BookingItem, item_id)
    problem = review_problem(item, user)
    if problem:
        raise ReviewError(problem)
    review = Review(booking_item_id=item.id, guide_id=item.guide_id, traveler_id=user.id,
                    rating=rating, comment=comment)
    db.session.add(review)
    try:
        db.session.commit()
    except IntegrityError:
        # booking_item_id is UNIQUE: a double-submit can't create two reviews
        db.session.rollback()
        raise ReviewError("You already reviewed this guide for this trip.")
    return review
