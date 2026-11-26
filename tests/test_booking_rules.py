"""The booking rules in services/booking.py.

The checkout page and the seed data both call create_booking(), so these
rules protect every booking.
"""
from datetime import date, timedelta

from extensions import db
from models import Booking, Flight, GuideProfile, Stay
from services.booking import BookingError, cancel_booking, create_booking
from tests.base import RihlaTestCase


class PasswordAndMoneyTests(RihlaTestCase):

    def test_passwords_are_hashed(self):
        maya = self.user("traveler@rihla.test")
        self.assertTrue(maya.password_hash.startswith("scrypt:"))
        self.assertNotIn("Traveler123!", maya.password_hash)
        self.assertTrue(maya.check_password("Traveler123!"))
        self.assertFalse(maya.check_password("wrong"))

    def test_every_booking_adds_up(self):
        """commission + amount owed to providers = total, and lines sum to the total."""
        for booking in Booking.query.all():
            self.assertEqual(booking.commission_cents + booking.provider_cents, booking.total_cents)
            self.assertEqual(sum(i.line_total_cents for i in booking.items), booking.total_cents)

    def test_guide_rating_is_the_average_of_reviews(self):
        aram = self.user("guide@rihla.test").guide_profile
        self.assertEqual(aram.average_rating(), 4.5)
        self.assertEqual(aram.review_count(), 2)


class SeatTests(RihlaTestCase):

    def setUp(self):
        super().setUp()
        self.maya = self.user("traveler@rihla.test")
        self.flight = Flight.query.filter_by(flight_number="RJ403").first()   # Amman, April 2027

    def book_flight(self, seats, traveler=None):
        return create_booking(traveler or self.maya, [{"type": "flight", "id": self.flight.id, "quantity": seats}],
                              self.flight.depart_date, self.flight.return_date)

    def test_overbooking_is_refused_and_nothing_changes(self):
        seats_before = self.flight.seats_available
        bookings_before = Booking.query.count()
        with self.assertRaises(BookingError):
            self.book_flight(seats_before + 1)
        db.session.refresh(self.flight)
        self.assertEqual(self.flight.seats_available, seats_before)
        self.assertEqual(Booking.query.count(), bookings_before)

    def test_booking_takes_seats_and_cancelling_gives_them_back(self):
        seats_before = self.flight.seats_available
        booking = self.book_flight(3)
        db.session.refresh(self.flight)
        self.assertEqual(self.flight.seats_available, seats_before - 3)
        cancel_booking(booking, self.maya)
        db.session.refresh(self.flight)
        self.assertEqual(self.flight.seats_available, seats_before)
        self.assertEqual(booking.status, "cancelled")

    def test_another_traveler_cannot_cancel(self):
        booking = self.book_flight(1)
        lara = self.user("lara@rihla.test")
        with self.assertRaises(BookingError):
            cancel_booking(booking, lara)


class RefusedBookingTests(RihlaTestCase):
    """Each case must raise BookingError and leave the seats untouched."""

    def test_invalid_trips_are_refused(self):
        maya = self.user("traveler@rihla.test")
        flight = Flight.query.filter_by(flight_number="ME311", depart_date=date(2027, 4, 16)).first()
        stay = Stay.query.filter_by(name="Paris Hotel Yerevan").first()
        egypt_stay = Stay.query.filter_by(name="Rixos Sharm El Sheikh").first()
        pending_guide = GuideProfile.query.filter_by(status="pending").first()
        later = date.today() + timedelta(days=30)
        seats_before = flight.seats_available

        cases = [
            ("pending guide", [{"type": "guide", "id": pending_guide.id, "quantity": 1}], later, later + timedelta(days=1)),
            ("two countries", [{"type": "flight", "id": flight.id, "quantity": 1},
                               {"type": "stay", "id": egypt_stay.id, "quantity": 2}], flight.depart_date, flight.return_date),
            ("dates differ from the flight", [{"type": "flight", "id": flight.id, "quantity": 1}], later, later + timedelta(days=3)),
            ("more nights than the trip", [{"type": "stay", "id": stay.id, "quantity": 9}], later, later + timedelta(days=3)),
            ("trip in the past", [{"type": "stay", "id": stay.id, "quantity": 1}], date(2026, 1, 1), date(2026, 1, 2)),
            ("two stays", [{"type": "stay", "id": stay.id, "quantity": 1},
                           {"type": "stay", "id": stay.id, "quantity": 1}], later, later + timedelta(days=3)),
        ]
        for label, items, start, end in cases:
            with self.subTest(label):
                with self.assertRaises(BookingError):
                    create_booking(maya, items, start, end)

        db.session.refresh(flight)
        self.assertEqual(flight.seats_available, seats_before)
