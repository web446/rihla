"""The Gemini agent (agent/gemini_agent.py), tested WITHOUT internet or an API key.

A fake client replaces Google's: it returns prepared answers (text or tool calls)
and remembers what our code sent. So these tests check OUR side: running the
tools for the right user, saving the history, the Confirm rule and the errors.
"""
import base64
import json
from datetime import date

from google.genai import errors, types

from agent import claude_agent, gemini_agent
from extensions import db
from models import Booking, BookingProposal, ChatMessage, Flight
from tests.base import RihlaTestCase, app
from tests.test_agent import AgentTestCase


# ---- building fake Gemini answers ----
def answer(*parts, finish=types.FinishReason.STOP):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=list(parts)), finish_reason=finish)])


def text(value):
    return types.Part(text=value)


def call(name, signature=None, **args):
    return types.Part(function_call=types.FunctionCall(id="call-" + name, name=name, args=args),
                      thought_signature=signature)


class FakeGemini:
    """Stands in for genai.Client: client.models.generate_content(...) returns the next prepared answer."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []          # the contents our code sent, one list per request
        self.models = self

    def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        next_answer = self.answers.pop(0)
        if isinstance(next_answer, Exception):
            raise next_answer
        return next_answer


class GeminiTestCase(AgentTestCase):

    def setUp(self):
        super().setUp()
        app.config["AI_PROVIDER"] = "gemini"
        app.config["AI_API_KEY"] = "test-key-not-real"
        self.real_make_client = gemini_agent.make_client

    def tearDown(self):
        gemini_agent.make_client = self.real_make_client
        super().tearDown()

    def use_fake(self, *answers):
        self.fake = FakeGemini(*answers)
        gemini_agent.make_client = lambda: self.fake
        return self.fake

    def chat(self, message):
        response = self.client.post("/api/chat", json={"message": message, "conversation_id": self.conversation},
                                    headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.conversation = data["conversation_id"]
        return data


class ModeTests(GeminiTestCase):

    def test_gemini_mode_needs_a_key(self):
        self.assertEqual(self.client.get("/api/conversations").get_json()["mode"], "gemini")
        app.config["AI_API_KEY"] = ""
        self.assertEqual(self.client.get("/api/conversations").get_json()["mode"], "demo")


class ToolLoopTests(GeminiTestCase):

    def test_tool_call_then_answer(self):
        self.use_fake(answer(call("search_flights", signature=b"sig-1", from_city="Beirut", to_country="Armenia")),
                      answer(text("Here are the next flights to Yerevan.")))
        data = self.chat("Flights to Armenia?")

        self.assertEqual(data["mode"], "gemini")
        reply = data["messages"][-1]
        self.assertEqual(reply["text"], "Here are the next flights to Yerevan.")
        self.assertTrue(reply["cards"])
        self.assertTrue(all(card["type"] == "flight" for card in reply["cards"]))

        # The 2nd request carried Gemini's call back with its signature, then our tool result.
        second = self.fake.requests[1]
        self.assertEqual(second[-2].parts[0].thought_signature, b"sig-1")
        response_part = second[-1].parts[0].function_response
        self.assertEqual(response_part.name, "search_flights")
        self.assertEqual(response_part.id, "call-search_flights")
        self.assertIn("output", response_part.response)

        # Saved in the same block format as the Claude agent
        saved = [json.loads(m.api_json) for m in ChatMessage.query.order_by(ChatMessage.id) if m.api_json]
        tool_use = saved[1][0]
        self.assertEqual(tool_use["type"], "tool_use")
        self.assertEqual(tool_use["input"]["month"], None)              # missing fields filled with None
        self.assertEqual(base64.b64decode(tool_use["gemini_signature"]), b"sig-1")
        self.assertEqual(saved[2][0]["type"], "tool_result")
        self.assertEqual(saved[2][0]["tool_use_id"], tool_use["id"])

    def test_booking_still_needs_confirm(self):
        flight = Flight.query.filter_by(flight_number="ME311", depart_date=date(2027, 4, 16)).first()
        bookings_before = Booking.query.count()
        # Gemini sends whole numbers as floats (7.0): they must still work.
        self.use_fake(answer(call("create_booking", flight_id=float(flight.id), seats=2.0)),
                      answer(text("Here is your summary. Click Confirm to book.")))
        card = self.chat("Book 2 seats on that flight")["messages"][-1]["cards"][0]

        self.assertEqual(card["type"], "summary")
        self.assertEqual(Booking.query.count(), bookings_before)            # nothing booked by the AI
        self.assertEqual(db.session.get(BookingProposal, card["proposal_id"]).status, "pending")

        self.press("confirm", card["proposal_id"])                         # the traveler confirms
        db.session.expire_all()
        self.assertEqual(Booking.query.count(), bookings_before + 1)
        self.assertEqual(Booking.query.order_by(Booking.id.desc()).first().source, "agent")

    def test_next_message_replays_the_saved_history(self):
        self.use_fake(answer(call("list_my_bookings", signature=b"sig-2")), answer(text("You have 2 trips.")))
        self.chat("My trips?")
        self.use_fake(answer(text("Sure!")))
        self.chat("Thanks")

        history = self.fake.requests[0]
        self.assertEqual([c.role for c in history], ["user", "model", "user", "model", "user"])
        self.assertEqual(history[1].parts[0].function_call.name, "list_my_bookings")
        self.assertEqual(history[1].parts[0].thought_signature, b"sig-2")     # restored from the database
        self.assertEqual(history[2].parts[0].function_response.name, "list_my_bookings")
        self.assertIn("Thanks", history[-1].parts[0].text)

    def test_other_users_trips_stay_private(self):
        # Trip 1 belongs to Lara: even if the AI asks, Maya's request can't touch it.
        self.use_fake(answer(call("cancel_booking", booking_id=1.0)), answer(text("I couldn't find that trip.")))
        self.chat("Cancel trip 1")
        saved = [json.loads(m.api_json) for m in ChatMessage.query.filter_by(role="tool")]
        self.assertTrue(saved[0][0]["is_error"])
        self.assertEqual(BookingProposal.query.filter_by(status="pending").count(), 0)


class ErrorTests(GeminiTestCase):

    def test_service_error_falls_back_to_demo_mode(self):
        quota = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
        self.use_fake(quota)
        data = self.chat("Where can I go without a visa?")
        self.assertEqual(data["mode"], "demo")
        self.assertIn("unavailable", data["messages"][-1]["text"])
        self.assertIn("Georgia", data["messages"][-1]["text"])

    def test_blocked_answer_gets_a_polite_refusal(self):
        self.use_fake(types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(role="model", parts=[]), finish_reason=types.FinishReason.SAFETY)]))
        reply = self.chat("something not allowed")["messages"][-1]
        self.assertIn("can't help with that", reply["text"])

    def test_too_many_tool_rounds_stops(self):
        self.use_fake(*[answer(call("list_my_bookings")) for _ in range(gemini_agent.MAX_TOOL_ROUNDS)])
        reply = self.chat("loop forever")["messages"][-1]
        self.assertIn("too many steps", reply["text"])


class ConversionTests(RihlaTestCase):
    """Pure functions: no requests needed."""

    def test_schemas_keep_only_real_required_fields(self):
        schemas = {d.name: d.parameters_json_schema for d in gemini_agent.FUNCTIONS}
        self.assertEqual(len(schemas), 9)
        self.assertEqual(schemas["search_flights"]["required"], ["from_city", "to_country"])
        self.assertEqual(schemas["search_flights"]["properties"]["month"]["type"], "integer")
        self.assertNotIn("required", schemas["create_booking"])
        self.assertIsNone(schemas["list_my_bookings"])

    def test_clean_args(self):
        args = gemini_agent.clean_args("search_hotels", {"country": "Jordan", "nights": 3.0})
        self.assertEqual(args, {"country": "Jordan", "nights": 3, "max_price_per_night_usd": None, "type": None})

    def test_claude_history_can_continue_on_gemini(self):
        """A chat started with Claude: thinking blocks are skipped and tool calls get the placeholder signature."""
        history = [
            {"role": "user", "content": [{"type": "text", "text": "Flights?"}]},
            {"role": "assistant", "content": [{"type": "thinking", "thinking": "", "signature": "x"},
                                              {"type": "tool_use", "id": "toolu_1", "name": "search_flights",
                                               "input": {"from_city": "Beirut", "to_country": "Jordan"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1",
                                          "content": "[]", "is_error": False}]},
        ]
        contents = gemini_agent.to_gemini(history)
        self.assertEqual(len(contents[1].parts), 1)
        self.assertEqual(contents[1].parts[0].thought_signature, gemini_agent.NO_SIGNATURE)
        self.assertEqual(contents[2].parts[0].function_response.name, "search_flights")
        self.assertEqual(contents[2].parts[0].function_response.response, {"output": []})

    def test_gemini_history_can_continue_on_claude(self):
        messages = [{"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_2", "name": "list_my_bookings", "input": {}, "gemini_signature": "c2ln"}]}]
        cleaned = claude_agent._without_gemini_fields(messages)
        self.assertNotIn("gemini_signature", cleaned[0]["content"][0])
        self.assertIn("gemini_signature", messages[0]["content"][0])     # the saved history is not changed
