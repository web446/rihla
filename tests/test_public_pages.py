"""Pages anyone can open, the trip-cost estimate and the search (services/search.py)."""
from datetime import date

from models import Country, Flight, GuideProfile, Stay
from services import search
from tests.base import RihlaTestCase


class PageTests(RihlaTestCase):

    def test_main_pages_open(self):
        for url in ("/", "/countries", "/credits"):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_every_country_page_opens(self):
        for country in Country.query.all():
            with self.subTest(country.slug):
                self.assertEqual(self.client.get(f"/countries/{country.slug}").status_code, 200)
        self.assertEqual(self.client.get("/countries/atlantis").status_code, 404)

    def test_search_box_redirects_to_the_chosen_country(self):
        response = self.client.get("/countries?to=armenia")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/countries/armenia"))

    def test_bad_search_filters_do_not_crash(self):
        response = self.client.get("/countries?month=99&days=abc&budget=NaN&interest=<script>")
        self.assertEqual(response.status_code, 200)

    def test_pending_guides_are_hidden(self):
        pending = GuideProfile.query.filter_by(status="pending").first()
        approved = GuideProfile.query.filter_by(status="approved").first()
        self.assertEqual(self.client.get(f"/guides/{approved.id}").status_code, 200)
        self.assertEqual(self.client.get(f"/guides/{pending.id}").status_code, 404)
        self.assertNotIn(pending.user.full_name, self.page(f"/countries/{pending.country.slug}"))


class EstimateTests(RihlaTestCase):
    """/api/estimate is used by the trip-cost calculator on the country page."""

    def estimate(self, query):
        return self.client.get("/api/estimate?" + query).get_json()

    def test_total_is_calculated_correctly(self):
        flight = Flight.query.filter_by(flight_number="ME311", depart_date=date(2027, 4, 16)).first()
        stay = Stay.query.filter_by(name="Paris Hotel Yerevan").first()
        aram = self.user("guide@rihla.test").guide_profile
        result = self.estimate(f"country=armenia&flight_id={flight.id}&stay_id={stay.id}&nights=6"
                               f"&guide_id={aram.id}&guide_days=2&days=7&travelers=2")
        # 2 seats x $330 + 6 nights x $110 + 2 days x $120 + 7 days x 2 people x $50 daily spend
        self.assertEqual(result["total_cents"], 2 * 33000 + 6 * 11000 + 2 * 12000 + 7 * 2 * 5000)

    def test_items_from_another_country_or_pending_guides_are_ignored(self):
        egypt_stay = Stay.query.filter_by(name="Rixos Sharm El Sheikh").first()
        self.assertEqual(self.estimate(f"country=armenia&stay_id={egypt_stay.id}&nights=3")["total_cents"], 0)
        pending = GuideProfile.query.filter_by(status="pending").first()
        result = self.estimate(f"country={pending.country.slug}&guide_id={pending.id}&guide_days=3")
        self.assertEqual(result["total_cents"], 0)

    def test_unknown_country_gives_a_json_404(self):
        response = self.client.get("/api/estimate?country=nowhere")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.is_json)


class SearchTests(RihlaTestCase):

    def test_warm_in_march(self):
        warm = {r["country"].slug for r in search.search_countries(month=3) if r["warm"]}
        self.assertEqual(warm, {"egypt", "malaysia"})

    def test_budget_filter(self):
        cheap = [r["country"].slug for r in search.search_countries(month=3, max_budget_cents=150000, days=5)]
        self.assertIn("egypt", cheap)
        self.assertNotIn("georgia", cheap)

    def test_interest_filter(self):
        beach = {r["country"].slug for r in search.search_countries(interests=["beach"])}
        self.assertEqual(beach, {"turkey", "egypt", "malaysia"})

    def test_guide_language_search(self):
        self.assertGreaterEqual(len(search.guides_with_ratings(language="arabic")), 4)
        # "%" is a wildcard in SQL LIKE; it must be treated as a normal character
        self.assertEqual(search.guides_with_ratings(language="%"), [])
