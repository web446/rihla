"""The AI travel agent in demo mode (agent/demo_agent.py, agent/chat.py, blueprints/agent.py).

Demo mode uses the same tools and the same "summary -> Confirm" rule as the
Claude version, so these tests also check the agent's safety rules:
the AI never books by itself, and a user can only see and change their own data.
"""
import json

from extensions import db
from models import Booking, BookingProposal, Flight
from tests.base import RihlaTestCase


class AgentTestCase(RihlaTestCase):

    def setUp(self):
        super().setUp()
        self.login("traveler@rihla.test", "Traveler123!")
        self.headers = {"X-CSRF-Token": self.token()}   # the chat sends the token in a header
        self.conversation = None

    def say(self, message):
        """Send a chat message and return the agent's last reply."""
        response = self.client.post("/api/chat", json={"message": message, "conversation_id": self.conversation},
                                    headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.conversation = data["conversation_id"]
        return data["messages"][-1]

    def press(self, button, proposal_id):
        """Click Confirm or Not now on a summary card."""
        return self.client.post(f"/api/{button}/{proposal_id}", headers=self.headers)


class SecurityTests(RihlaTestCase):

    def test_chat_needs_login_and_csrf_token(self):
        self.assertIn(self.client.post("/api/chat", json={"message": "hi"}).status_code, (400, 401))
        self.login("traveler@rihla.test", "Traveler123!")
        response = self.client.post("/api/chat", json={"message": "hi"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.is_json)


class AnswerTests(AgentTestCase):

    def test_trip_ideas_flights_and_guides(self):
        reply = self.say("I want somewhere warm in March for 5 days, budget $1500")
        self.assertLessEqual({"Egypt", "Malaysia"}, {card["title"] for card in reply["cards"]})

        reply = self.say("find flights to Armenia")
        self.assertTrue(reply["cards"])
        self.assertTrue(all(card["type"] == "flight" for card in reply["cards"]))

        reply = self.say("guides in Jordan speaking French")
        self.assertEqual([card["title"] for card in reply["cards"]], ["Lina Haddadin"])

    def test_visa_questions(self):
        text = self.say("Where can I go without a visa?")["text"]
        for country in ("Turkey", "Armenia", "Egypt", "Jordan", "Georgia", "Malaysia"):
            self.assertIn(country, text)
        text = self.say("Do I need a visa for Georgia?")["text"]
        self.assertIn("insurance", text)
        self.assertIn("1 year", text)

    def test_unknown_message_gets_help(self):
        self.assertIn("demo mode", self.say("blah blah")["text"])


class BookingTests(AgentTestCase):

    def test_agent_only_books_after_confirm(self):
        bookings_before = Booking.query.count()
        hotel_card = self.say("book the cheapest hotel in Armenia")["cards"][0]
        self.assertEqual(hotel_card["type"], "summary")
        self.assertEqual(Booking.query.count(), bookings_before)                 # nothing booked yet
        self.assertEqual(db.session.get(BookingProposal, hotel_card["proposal_id"]).status, "pending")

        # A new summary replaces the old one, which can no longer be confirmed
        egypt_card = self.say("plan a trip to Egypt")["cards"][0]
        db.session.expire_all()
        self.assertEqual(db.session.get(BookingProposal, hotel_card["proposal_id"]).status, "expired")
        reply = self.press("confirm", hotel_card["proposal_id"]).get_json()["messages"][-1]
        self.assertIn("already used or replaced", reply["text"])

        payload = json.loads(db.session.get(BookingProposal, egypt_card["proposal_id"]).payload_json)
        flight_id = next(item["id"] for item in payload["items"] if item["type"] == "flight")
        seats_before = db.session.get(Flight, flight_id).seats_available

        self.say("confirm")                                                      # typing confirm works too
        db.session.expire_all()
        booking = Booking.query.order_by(Booking.id.desc()).first()
        self.assertEqual(Booking.query.count(), bookings_before + 1)
        self.assertEqual(booking.source, "agent")
        self.assertEqual(db.session.get(Flight, flight_id).seats_available, seats_before - 1)
        self.assertEqual(booking.commission_cents + booking.provider_cents, booking.total_cents)

        self.say("confirm")                                                      # nothing pending any more
        self.assertEqual(Booking.query.count(), bookings_before + 1)

        reply = self.say("my bookings")
        self.assertTrue(any(card.get("booking_id") == booking.id for card in reply["cards"]))

    def test_cancel_through_the_agent_also_needs_confirm(self):
        self.say("plan a trip to Egypt")
        self.say("confirm")
        booking = Booking.query.order_by(Booking.id.desc()).first()

        card = self.say(f"cancel trip {booking.id}")["cards"][0]
        self.press("decline", card["proposal_id"])
        db.session.expire_all()
        self.assertEqual(db.session.get(Booking, booking.id).status, "confirmed")

        card = self.say(f"cancel trip {booking.id}")["cards"][0]
        self.press("confirm", card["proposal_id"])
        db.session.expire_all()
        self.assertEqual(db.session.get(Booking, booking.id).status, "cancelled")


class PrivacyTests(AgentTestCase):

    def test_users_only_reach_their_own_trips_and_chats(self):
        reply = self.say("cancel trip 1")                   # trip 1 belongs to Lara
        self.assertIn("no trip #1", reply["text"].lower())
        card = self.say("book the cheapest hotel in Armenia")["cards"][0]
        maya_chat = self.conversation
        self.assertGreater(len(self.client.get(f"/api/conversations/{maya_chat}").get_json()["messages"]), 2)

        self.logout()
        self.login("lara@rihla.test", "Traveler123!")
        lara = {"X-CSRF-Token": self.token()}
        self.assertEqual(self.client.get(f"/api/conversations/{maya_chat}").status_code, 404)
        self.assertEqual(self.client.post(f"/api/confirm/{card['proposal_id']}", headers=lara).status_code, 400)
        response = self.client.post("/api/chat", json={"message": "hi", "conversation_id": maya_chat}, headers=lara)
        self.assertNotEqual(response.get_json()["conversation_id"], maya_chat)


class RateLimitTests(AgentTestCase):

    def test_too_many_messages_get_429(self):
        from tests.base import app
        app.config["CHAT_LIMIT_PER_HOUR"] = 3
        codes = [self.client.post("/api/chat", json={"message": "hello"}, headers=self.headers).status_code
                 for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])
