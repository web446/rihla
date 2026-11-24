"""Log in, sign up, roles and CSRF (blueprints/auth.py and security.py)."""
from models import GuideProfile, User
from tests.base import RihlaTestCase


class LoginTests(RihlaTestCase):

    def test_private_pages_redirect_to_login(self):
        response = self.client.get("/me/trips")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_form_without_csrf_token_is_refused(self):
        response = self.client.post("/login", data={"email": "traveler@rihla.test", "password": "Traveler123!"})
        self.assertEqual(response.status_code, 400)

    def test_wrong_password_and_unknown_email_get_the_same_message(self):
        token = self.token("/login")
        wrong = self.client.post("/login", data={"csrf_token": token, "email": "traveler@rihla.test", "password": "wrong"})
        unknown = self.client.post("/login", data={"csrf_token": token, "email": "nobody@rihla.test", "password": "wrong"})
        self.assertEqual(wrong.status_code, 400)
        self.assertIn(b"Wrong email or password", wrong.data)
        self.assertIn(b"Wrong email or password", unknown.data)

    def test_login_ignores_email_case_and_goes_to_my_trips(self):
        response = self.login("TRAVELER@rihla.test ", "Traveler123!")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/me/trips"))
        self.assertEqual(self.client.get("/me/trips").status_code, 200)

    def test_each_role_only_opens_its_own_pages(self):
        self.login("traveler@rihla.test", "Traveler123!")
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertEqual(self.client.get("/guide/dashboard").status_code, 403)
        self.logout()
        self.login("guide@rihla.test", "Guide123!")
        self.assertEqual(self.client.get("/admin/guides").status_code, 403)
        self.assertEqual(self.client.get("/me/basket").status_code, 403)

    def test_logout_must_be_a_post(self):
        self.login("traveler@rihla.test", "Traveler123!")
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.logout()
        self.assertEqual(self.client.get("/me/trips").status_code, 302)

    def test_next_link_to_another_site_is_ignored(self):
        response = self.client.post("/login", data={"csrf_token": self.token("/login"), "email": "admin@rihla.test",
                                                    "password": "Admin123!", "next": "https://evil.com"})
        self.assertTrue(response.location.endswith("/admin/"))

    def test_unknown_page_is_404(self):
        self.assertEqual(self.client.get("/nowhere").status_code, 404)


class SignUpTests(RihlaTestCase):

    def sign_up(self, **fields):
        data = {"csrf_token": self.token("/register"), "full_name": "Test Person", "email": "new@rihla.test",
                "password": "Passw0rdX", "confirm_password": "Passw0rdX"}
        data.update(fields)
        return self.client.post("/register", data=data)

    def test_invalid_sign_up_shows_errors_and_not_the_password(self):
        response = self.sign_up(full_name="A", email="bad", password="short", confirm_password="x")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"is-invalid", response.data)
        self.assertNotIn(b'value="short"', response.data)

    def test_valid_sign_up_creates_a_traveler_with_a_hashed_password(self):
        self.assertEqual(self.sign_up().status_code, 302)
        user = User.query.filter_by(email="new@rihla.test").first()
        self.assertEqual(user.role, "traveler")
        self.assertTrue(user.password_hash.startswith("scrypt:"))

    def test_email_can_only_be_used_once(self):
        self.sign_up()
        self.logout()
        response = self.sign_up(full_name="Again")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"already exists", response.data)


class GuideSignUpTests(RihlaTestCase):

    def guide_form(self, **fields):
        data = {"csrf_token": self.token("/register/guide"), "full_name": "Rami Guide", "email": "rami@rihla.test",
                "password": "Guide1234", "confirm_password": "Guide1234", "country_id": "1",
                "price_per_day": "95", "languages": "Arabic, English,",
                "bio": "I have guided in Istanbul for ten years and love street food."}
        data.update(fields)
        return self.client.post("/register/guide", data=data)

    def test_new_guide_waits_for_approval(self):
        response = self.guide_form()
        self.assertTrue(response.location.endswith("/guide/dashboard"))
        profile = GuideProfile.query.join(User).filter(User.email == "rami@rihla.test").first()
        self.assertEqual(profile.status, "pending")
        self.assertEqual(profile.price_per_day_cents, 9500)
        self.assertEqual(profile.languages, "Arabic, English")
        self.assertIn(b"pending", self.client.get("/guide/dashboard").data)

    def test_fake_country_and_bad_values_are_refused(self):
        response = self.guide_form(email="fake@rihla.test", country_id="999", price_per_day="5",
                                   languages="", bio="short")
        self.assertEqual(response.status_code, 400)
        self.assertGreaterEqual(response.data.count(b"invalid-feedback"), 4)
