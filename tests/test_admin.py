"""Admin dashboard, content management and commission setting (blueprints/admin.py)."""
from datetime import date

from extensions import db
from models import Booking, Country, Flight, Monument, Stay
from services.booking import create_booking
from services.pricing import get_commission_rate
from tests.base import RihlaTestCase

NEW_COUNTRY = {
    "name": "Portugal", "slug": "portugal", "tagline": "Tiles, tarts and Atlantic light.",
    "description": "Lisbon, Porto and the Algarve coast.", "best_time": "April to October",
    "currency": "Euro (EUR)", "language": "Portuguese", "warm_months": "6,5,7,7", "tags": "beach,food",
    "avg_daily_spend_cents": "70", "hero_image": "", "entry_type": "evisa", "max_stay": "90 days",
    "entry_notes": "", "popularity": "2", "popularity_note": "",
}


class AdminTestCase(RihlaTestCase):
    def setUp(self):
        super().setUp()
        self.login("admin@rihla.test", "Admin123!")
        self.csrf = self.token()

    def post(self, url, **fields):
        return self.client.post(url, data={"csrf_token": self.csrf, **fields})


class AccessTests(RihlaTestCase):
    def test_travelers_cannot_open_admin_pages(self):
        self.login("traveler@rihla.test", "Traveler123!")
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertEqual(self.client.get("/admin/content/flights").status_code, 403)


class DashboardTests(AdminTestCase):

    def test_dashboard_shows_the_commission_earned(self):
        commission = db.session.execute(
            db.select(db.func.sum(Booking.commission_cents)).where(Booking.status == "confirmed")).scalar()
        self.assertIn(f"${commission / 100:,.2f}", self.page("/admin/"))

    def test_content_lists_and_forms_open(self):
        for key in ("countries", "monuments", "restaurants", "stays", "flights"):
            with self.subTest(key):
                self.assertEqual(self.client.get(f"/admin/content/{key}").status_code, 200)
                self.assertEqual(self.client.get(f"/admin/content/{key}/new").status_code, 200)
        self.assertEqual(self.client.get("/admin/content/users").status_code, 404)
        self.assertNotIn("Garni Temple", self.page("/admin/content/monuments?country=jordan"))

    def test_bookings_page_can_be_filtered(self):
        self.assertIn("Maya Khoury", self.page("/admin/bookings?status=confirmed"))


class ContentTests(AdminTestCase):

    def test_create_a_country_and_a_monument_then_edit_it(self):
        response = self.post("/admin/content/countries/new", **NEW_COUNTRY)
        portugal = Country.query.filter_by(slug="portugal").first()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(portugal.warm_months, "5,6,7")           # sorted, duplicates removed
        self.assertEqual(portugal.avg_daily_spend_cents, 7000)    # dollars -> cents
        self.assertEqual(self.client.get("/countries/portugal").status_code, 200)

        self.post("/admin/content/monuments/new", country_id=str(portugal.id), name="Belem Tower",
                  city="Lisbon", entry_cost_cents="10.50", description="A 16th-century fortress on the Tagus river.")
        tower = Monument.query.filter_by(name="Belem Tower").first()
        self.assertEqual(tower.entry_cost_cents, 1050)

        self.post(f"/admin/content/monuments/{tower.id}/edit", country_id=str(portugal.id), name="Belem Tower",
                  city="Lisbon", entry_cost_cents="0", description="A 16th-century fortress on the Tagus river.")
        db.session.expire_all()
        self.assertEqual(tower.entry_cost_cents, 0)

    def test_invalid_country_is_refused(self):
        bad = dict(NEW_COUNTRY, slug="Bad Slug!", avg_daily_spend_cents="-5", hero_image="javascript:alert(1)")
        response = self.post("/admin/content/countries/new", **bad)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn("lowercase", body)
        self.assertIn("https://", body)

    def flight_form(self, **changes):
        armenia = Country.query.filter_by(slug="armenia").first()
        data = {"country_id": str(armenia.id), "airline": "Middle East Airlines", "flight_number": "ME999",
                "to_city": "Yerevan", "stops": "Direct", "depart_date": "2027-05-01",
                "return_date": "2027-05-08", "price_cents": "450", "seats_total": "20"}
        data.update(changes)
        return data

    def test_flight_dates_and_seats_are_checked(self):
        response = self.post("/admin/content/flights/new", **self.flight_form(return_date="2027-04-20"))
        self.assertEqual(response.status_code, 400)               # return before departure

        self.post("/admin/content/flights/new", **self.flight_form())
        flight = Flight.query.filter_by(flight_number="ME999").first()
        self.assertEqual(flight.seats_available, 20)

        maya = self.user("traveler@rihla.test")
        create_booking(maya, [{"type": "flight", "id": flight.id, "quantity": 3}], flight.depart_date, flight.return_date)
        response = self.post(f"/admin/content/flights/{flight.id}/edit", **self.flight_form(seats_total="2"))
        self.assertEqual(response.status_code, 400)               # 3 seats already sold
        self.assertIn("already booked", response.get_data(as_text=True))

        self.post(f"/admin/content/flights/{flight.id}/edit", **self.flight_form(seats_total="30"))
        db.session.expire_all()
        self.assertEqual((flight.seats_total, flight.seats_available), (30, 27))

    def test_booked_or_used_items_cannot_be_deleted(self):
        stay = Stay.query.filter_by(name="Paris Hotel Yerevan").first()
        armenia = Country.query.filter_by(slug="armenia").first()
        self.post(f"/admin/content/stays/{stay.id}/delete")
        self.post(f"/admin/content/countries/{armenia.id}/delete")
        self.assertIsNotNone(db.session.get(Stay, stay.id))
        self.assertIsNotNone(db.session.get(Country, armenia.id))
        self.assertEqual(self.client.get("/admin/content/monuments/1/delete").status_code, 405)

    def test_unused_monument_is_deleted(self):
        monument = Monument.query.first()
        self.post(f"/admin/content/monuments/{monument.id}/delete")
        self.assertIsNone(db.session.get(Monument, monument.id))


class CommissionTests(AdminTestCase):

    def test_new_rate_applies_to_new_bookings_only(self):
        self.post("/admin/settings", commission_rate="12.5")
        db.session.expire_all()
        self.assertEqual(get_commission_rate(), 12.5)

        maya = self.user("traveler@rihla.test")
        stay = Stay.query.filter_by(name="Rooms Hotel Tbilisi").first()
        booking = create_booking(maya, [{"type": "stay", "id": stay.id, "quantity": 2}],
                                 date(2027, 6, 1), date(2027, 6, 3))
        self.assertEqual(booking.commission_rate, 12.5)
        self.assertEqual(booking.commission_cents, 4250)
        self.assertEqual(db.session.get(Booking, 1).commission_rate, 10.0)

    def test_unreasonable_rates_are_refused(self):
        for rate in ("80", "nan", "-1"):
            with self.subTest(rate):
                self.assertEqual(self.post("/admin/settings", commission_rate=rate).status_code, 400)
