"""Guide reviews, the guide dashboard and guide approval by the admin."""
from extensions import db
from models import Booking, BookingItem, Review
from tests.base import RihlaTestCase


class ReviewTests(RihlaTestCase):

    def setUp(self):
        super().setUp()
        self.maya = self.user("traveler@rihla.test")
        self.mehmet = self.user("mehmet@rihla.test").guide_profile
        # Maya's past Cappadocia trip with guide Mehmet (in the sample data)
        self.past_item = (BookingItem.query.join(Booking)
                          .filter(Booking.traveler_id == self.maya.id, BookingItem.guide_id == self.mehmet.id).first())

    def review(self, item_id, rating, comment):
        return self.client.post(f"/me/trips/review/{item_id}",
                                data={"csrf_token": self.token(), "rating": rating, "comment": comment})

    def test_traveler_rates_the_guide_of_a_past_trip_once(self):
        self.login("traveler@rihla.test", "Traveler123!")
        trips = self.page("/me/trips")
        self.assertIn("Rate your guide", trips)
        self.assertIn(f"/me/trips/review/{self.past_item.id}", trips)

        self.assertEqual(self.review(self.past_item.id, "9", "short").status_code, 400)
        response = self.review(self.past_item.id, "5", "Amazing hike through the valleys at sunrise!")
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertEqual(self.mehmet.average_rating(), 5.0)

        self.review(self.past_item.id, "1", "Trying to review twice!!")
        self.assertEqual(Review.query.filter_by(booking_item_id=self.past_item.id).count(), 1)
        self.assertIn("You rated", self.page("/me/trips"))

    def test_future_trips_cannot_be_rated(self):
        future_item = (BookingItem.query.join(Booking)
                       .filter(Booking.traveler_id == self.maya.id, Booking.start_date > db.func.current_date()).first())
        self.login("traveler@rihla.test", "Traveler123!")
        self.assertEqual(self.client.get(f"/me/trips/review/{future_item.id}").status_code, 302)

    def test_only_the_traveler_who_booked_can_rate(self):
        self.login("lara@rihla.test", "Traveler123!")
        self.review(self.past_item.id, "1", "Not my booking at all")
        self.assertEqual(Review.query.filter_by(booking_item_id=self.past_item.id).count(), 0)

    def test_hotels_cannot_be_rated(self):
        lara = self.user("lara@rihla.test")
        stay_item = (BookingItem.query.join(Booking)
                     .filter(Booking.traveler_id == lara.id, BookingItem.item_type == "stay").first())
        self.login("lara@rihla.test", "Traveler123!")
        self.assertEqual(self.client.get(f"/me/trips/review/{stay_item.id}").status_code, 302)


class GuideDashboardTests(RihlaTestCase):

    def test_dashboard_shows_earnings_after_commission(self):
        self.login("guide@rihla.test", "Guide123!")
        page = self.page("/guide/dashboard")
        self.assertIn("$324.00", page)      # $360 of guiding minus 10% commission
        self.assertIn("live!", page)
        self.assertIn("4.5", page)

    def test_approved_guide_edits_profile_and_stays_approved(self):
        aram = self.user("guide@rihla.test").guide_profile
        self.login("guide@rihla.test", "Guide123!")
        self.client.post("/guide/profile", data={
            "csrf_token": self.token(), "country_id": str(aram.country_id), "languages": "Armenian, English",
            "bio": "Archaeologist showing you Armenia's monasteries for ten years.", "price_per_day": "130"})
        db.session.expire_all()
        self.assertEqual(aram.price_per_day_cents, 13000)
        self.assertEqual(aram.status, "approved")


class GuideApprovalTests(RihlaTestCase):

    def setUp(self):
        super().setUp()
        self.nino = self.user("nino@rihla.test").guide_profile     # pending in the sample data

    def set_status(self, status):
        # follow_redirects=True opens the admin page like a browser would, which also shows (and
        # clears) the "Nino Kapanadze was ..." message, so it can't appear on the next page we check.
        self.client.post(f"/admin/guides/{self.nino.id}/status", follow_redirects=True,
                         data={"csrf_token": self.token(), "status": status})
        db.session.expire_all()

    def test_admin_approves_then_rejects_a_guide(self):
        self.assertNotIn("Nino Kapanadze", self.page("/countries/georgia"))
        self.login("admin@rihla.test", "Admin123!")
        self.assertIn("Nino Kapanadze", self.page("/admin/guides"))

        self.set_status("approved")
        self.assertEqual(self.nino.status, "approved")
        self.assertIn("Nino Kapanadze", self.page("/countries/georgia"))

        self.set_status("hacked")                      # not a real status
        self.assertEqual(self.nino.status, "approved")

        self.set_status("rejected")
        self.assertEqual(self.nino.status, "rejected")
        self.assertNotIn("Nino Kapanadze", self.page("/countries/georgia"))

    def test_rejected_guide_who_edits_the_profile_goes_back_to_pending(self):
        self.nino.status = "rejected"
        db.session.commit()
        self.login("nino@rihla.test", "Guide123!")
        self.assertIn("not approved", self.page("/guide/dashboard"))
        self.client.post("/guide/profile", data={
            "csrf_token": self.token(), "country_id": str(self.nino.country_id), "languages": "Georgian, English",
            "bio": "Tbilisi wine and food guide with 8 years of experience guiding visitors.", "price_per_day": "150"})
        db.session.expire_all()
        self.assertEqual(self.nino.status, "pending")
