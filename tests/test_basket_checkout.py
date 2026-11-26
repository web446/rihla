"""Trip basket, simulated checkout and My Trips (blueprints/traveler.py)."""
from datetime import date, timedelta

from extensions import db
from models import Booking, Flight, GuideProfile, Stay, User
from tests.base import RihlaTestCase


class BasketTests(RihlaTestCase):

    def setUp(self):
        super().setUp()
        self.flight = Flight.query.filter_by(flight_number="ME311", depart_date=date(2027, 4, 16)).first()
        self.stay = Stay.query.filter_by(name="Paris Hotel Yerevan").first()
        self.aram = self.user("guide@rihla.test").guide_profile

    def start(self):
        """Log in as Maya and remember a CSRF token for the forms."""
        self.login("traveler@rihla.test", "Traveler123!")
        self.csrf = self.token()

    def add(self, item_type, item_id, quantity):
        return self.client.post("/me/basket/add", data={
            "csrf_token": self.csrf, "item_type": item_type, "item_id": item_id,
            "quantity": quantity, "next": "/countries/armenia"})

    def fill_basket(self):
        self.add("flight", self.flight.id, 2)     # 2 x $330
        self.add("stay", self.stay.id, 7)         # 7 x $110
        self.add("guide", self.aram.id, 2)        # 2 x $120

    def checkout(self):
        return self.client.post("/me/checkout", data={"csrf_token": self.csrf, "confirm_simulated": "yes"})

    # ---- tests ----
    def test_visitors_must_log_in_to_book(self):
        page = self.page("/countries/armenia")
        self.assertIn("Log in to book", page)
        self.assertNotIn("/me/basket/add", page)
        self.start()
        self.assertIn("Add to trip", self.page("/countries/armenia"))

    def test_basket_shows_the_right_total(self):
        self.start()
        self.fill_basket()
        self.assertIn("$1,670.00", self.page("/me/basket"))

    def test_bad_items_are_not_added(self):
        self.start()
        response = self.add("flight", self.flight.id, 50)          # more seats than allowed
        self.assertFalse(response.location.endswith("/me/basket"))
        pending = GuideProfile.query.filter_by(status="pending").first()
        self.add("guide", pending.id, 1)                           # guide not approved
        self.add("users", 1, 1)                                    # not a bookable type
        self.assertIn("Your basket is empty", self.page("/me/basket"))

    def test_checkout_needs_the_simulated_payment_box(self):
        self.start()
        self.fill_basket()
        response = self.client.post("/me/checkout", data={"csrf_token": self.csrf})
        self.assertEqual(response.status_code, 400)

    def test_checkout_creates_the_booking(self):
        self.start()
        self.fill_basket()
        seats_before = self.flight.seats_available
        count_before = Booking.query.count()

        response = self.checkout()
        self.assertIn("/me/trips?new=", response.location)
        self.assertEqual(Booking.query.count(), count_before + 1)

        booking = Booking.query.order_by(Booking.id.desc()).first()
        self.assertEqual(booking.total_cents, 167000)
        self.assertEqual(booking.commission_cents, 16700)    # 10%
        self.assertEqual(booking.provider_cents, 150300)
        self.assertEqual(booking.start_date, self.flight.depart_date)
        db.session.refresh(self.flight)
        self.assertEqual(self.flight.seats_available, seats_before - 2)
        self.assertIn("Your basket is empty", self.page("/me/basket"))
        trips = self.page(f"/me/trips?new={booking.id}")
        self.assertIn(f"Trip #{booking.id}", trips)
        self.assertIn("postmark", trips)                     # the BOOKED stamp

    def test_cancel_gives_seats_back_only_once(self):
        self.start()
        self.fill_basket()
        seats_before = self.flight.seats_available
        self.checkout()
        booking = Booking.query.order_by(Booking.id.desc()).first()

        self.client.post(f"/me/trips/{booking.id}/cancel", data={"csrf_token": self.csrf})
        db.session.refresh(self.flight)
        db.session.refresh(booking)
        self.assertEqual(booking.status, "cancelled")
        self.assertEqual(self.flight.seats_available, seats_before)

        self.client.post(f"/me/trips/{booking.id}/cancel", data={"csrf_token": self.csrf})
        self.assertIn("already cancelled", self.page("/me/trips"))

    def test_travelers_cannot_see_or_cancel_each_others_trips(self):
        maya_trip = (Booking.query.join(User)
                     .filter(User.email == "traveler@rihla.test", Booking.status == "confirmed",
                             Booking.start_date > date.today()).first())
        self.login("lara@rihla.test", "Traveler123!")
        self.client.post(f"/me/trips/{maya_trip.id}/cancel", data={"csrf_token": self.token()})
        db.session.refresh(maya_trip)
        self.assertEqual(maya_trip.status, "confirmed")
        self.assertNotIn(f"Trip #{maya_trip.id}", self.page("/me/trips"))

    def test_stay_only_trip_needs_dates(self):
        self.start()
        self.add("stay", self.stay.id, 3)
        self.assertEqual(self.client.get("/me/checkout").status_code, 302)    # no dates yet
        start = date.today() + timedelta(days=30)
        self.client.post("/me/basket/update", data={"csrf_token": self.csrf, "qty_stay": 3,
                                                    "start": start.isoformat(),
                                                    "end": (start + timedelta(days=3)).isoformat()})
        self.assertEqual(self.client.get("/me/checkout").status_code, 200)
        self.assertIn("new=", self.checkout().location)
