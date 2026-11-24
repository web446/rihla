"""Demo mode: a simple rule-based agent used when no AI key is configured.

It understands a few fixed kinds of requests with regular expressions and
calls the SAME tools as the Claude agent (agent/tools.py), so searching,
the summary cards and the Confirm step work exactly the same way. This
keeps the chat working during a presentation even without internet or a key.

Examples it understands:
    "somewhere warm in March for 5 days, budget $1500"
    "find flights to Italy"            "hotels in Japan"
    "book the cheapest hotel in Japan" "plan a trip to Egypt"
    "guides in Greece speaking Arabic" "tell me about Turkey"
    "book flight 12"   "book stay 7"   "book guide 3"
    "my bookings"      "cancel trip 6"
"""
import calendar
import re

from services import search
from services.pricing import format_money

from agent.tools import run_tool

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
LANGUAGES = ("english", "arabic", "french", "italian", "japanese", "greek", "turkish", "spanish",
             "german", "thai", "chinese")
HELP = ("I'm in demo mode, so I understand a few kinds of requests. Try:\n"
        "• \"Somewhere warm in March for 5 days, budget $1500\"\n"
        "• \"Find flights to Italy\" or \"Hotels in Japan\"\n"
        "• \"Plan a trip to Egypt\" or \"Book the cheapest hotel in Japan\"\n"
        "• \"Guides in Greece speaking Arabic\"\n"
        "• \"My bookings\" or \"Cancel trip 6\"")


def find_country(text):
    lower = text.lower()
    for country in search.all_countries():
        if re.search(rf"\b{re.escape(country.name.lower())}\b", lower):
            return country
    return None


def find_month(text):
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in MONTHS:
            return MONTHS[word]
    return None


def _number(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


class DemoAgent:
    """Each reply is (text, cards). Every tool call goes through run_tool()."""

    def __init__(self, user, conversation_id):
        self.user = user
        self.conversation_id = conversation_id
        self.cards = []

    def call(self, tool, **args):
        result = run_tool(tool, args, self.user, self.conversation_id)
        if not result.is_error:
            self.cards.extend(result.cards)
        return result

    def reply(self, message):
        text = self.answer(message.strip())
        return text, self.cards

    # ------------------------------------------------------------------
    def answer(self, msg):
        lower = msg.lower()
        country = find_country(msg)

        if re.search(r"\b(my (bookings|trips|reservations))\b", lower):
            result = self.call("list_my_bookings")
            count = len(result.data["bookings"])
            return f"You have {count} trip(s) with Rihla:" if count else "You have no trips yet. Where would you like to go?"

        match = re.search(r"\bcancel\b.*?#?(\d+)", lower)
        if match:
            result = self.call("cancel_booking", booking_id=int(match.group(1)))
            if result.is_error:
                return result.data["error"]
            return "Here's what would be cancelled. Click **Confirm** (or type \"confirm\") to cancel it."

        match = re.search(r"\bbook\b.*?\b(flight|stay|hotel|apartment|guide)\b\s*#?(\d+)", lower)
        if match:
            return self.book_item(match.group(1), int(match.group(2)), msg)

        if re.search(r"\b(book|reserve)\b", lower) and re.search(r"\b(cheapest|cheap)\b", lower) and country:
            return self.package(country, with_guide="guide" in lower)

        if re.search(r"\b(plan|organi[sz]e)\b", lower) and country:
            return self.package(country, with_guide=True)

        if "flight" in lower and country:
            month = find_month(msg)
            result = self.call("search_flights", from_city="Beirut", to_country=country.name, month=month)
            flights = result.data["flights"]
            if not flights:
                return f"No upcoming flights to {country.name}" + (" that month." if month else ".")
            return (f"Here are {len(flights)} flight(s) from Beirut to {country.name}. "
                    "Press **Book** on one to prepare a booking.")

        if re.search(r"\b(hotel|hotels|stay|stays|apartment|sleep)\b", lower) and country:
            budget = _number(r"(?:under|below|max|\$)\s*\$?(\d+)", msg)
            result = self.call("search_hotels", country=country.name, nights=None,
                               max_price_per_night_usd=budget, type=None)
            return f"Places to stay in {country.name}, cheapest first:" if result.data["stays"] else \
                f"No stays in {country.name} match that budget."

        if "guide" in lower and country:
            language = next((lang for lang in LANGUAGES if lang in lower), None)
            result = self.call("list_guides", country=country.name, language=language, max_price_per_day_usd=None)
            if not result.data["guides"]:
                return f"No approved guides in {country.name}" + (f" speak {language.title()}." if language else ".")
            return f"Approved guides in {country.name}" + (f" who speak {language.title()}" if language else "") + ":"

        month = find_month(msg)
        budget = (_number(r"\$\s*([\d,]+)", msg) or _number(r"budget\D{0,12}([\d,]+)", lower)
                  or _number(r"([\d,]+)\s*(?:usd|dollars)", lower))
        days = _number(r"(\d+)\s*(?:days|day|nights)", msg)
        interest = next((t for t in search.all_interests() if t in lower), None)
        if month or budget or "warm" in lower or "where" in lower or "suggest" in lower or (interest and not country):
            result = self.call("search_countries", month=month, max_budget_usd=budget, days=days,
                               interests=[interest] if interest else None, travelers=None)
            results = result.data["results"]
            if not results:
                return "Nothing fits those filters. Try a bigger budget or fewer days."
            warm = [r["country"] for r in results if r["warm_that_month"]]
            intro = f"Warm in {calendar.month_name[month]}: {', '.join(warm)}. " if month and warm else ""
            best = results[0]
            return (f"{intro}Best match: **{best['country']}**, about "
                    f"{format_money(int(best['estimated_total_usd'] * 100))} for {result.data['days']} days. "
                    f"Say \"plan a trip to {best['country']}\" and I'll put a full trip together.")

        if country:
            result = self.call("get_country_details", country=country.name)
            d = result.data
            sights = ", ".join(m["name"] for m in d["monuments"][:3])
            return (f"**{d['country']}**: {d['description']} Best time: {d['best_time']}. Must-see: {sights}. "
                    f"Try \"flights to {d['country']}\" or \"plan a trip to {d['country']}\".")

        return HELP

    # ------------------------------------------------------------------
    def package(self, country, with_guide):
        """Next flight + cheapest stay for the whole trip (+ top guide 2 days) -> summary to confirm."""
        flights = self.call("search_flights", from_city="Beirut", to_country=country.name, month=None, date=None)
        if not flights.data["flights"]:
            return f"There are no upcoming flights to {country.name} right now."
        flight = flights.data["flights"][0]
        stays = self.call("search_hotels", country=country.name, nights=flight["nights"],
                          max_price_per_night_usd=None, type=None).data["stays"]
        guide_id = None
        if with_guide:
            guides = self.call("list_guides", country=country.name, language=None, max_price_per_day_usd=None).data["guides"]
            guide_id = guides[0]["guide_id"] if guides else None
        self.cards = []  # only show the summary card for a package
        result = self.call("create_booking", flight_id=flight["flight_id"], seats=1,
                           stay_id=stays[0]["stay_id"] if stays else None, nights=flight["nights"],
                           guide_id=guide_id, guide_days=2 if guide_id else None, start_date=None, end_date=None)
        if result.is_error:
            return f"I couldn't prepare that trip: {result.data['error']}"
        return (f"Here's the best-value trip to {country.name}: the next flight from Beirut, the cheapest stay"
                + (" and a top-rated guide for 2 days" if guide_id else "")
                + ". Nothing is booked yet: click **Confirm** (or type \"confirm\") to book it.")

    def book_item(self, kind, item_id, msg):
        """'Book flight 12' / 'Book stay 7' / 'Book guide 3' (sent by the cards' Book buttons)."""
        quantity = _number(r"for\s+(\d+)", msg)
        from models import Flight, GuideProfile, Stay
        from extensions import db
        model = {"flight": Flight, "stay": Stay, "hotel": Stay, "apartment": Stay, "guide": GuideProfile}[kind]
        obj = db.session.get(model, item_id)
        if obj is None:
            return f"I can't find {kind} {item_id}."
        if model is Flight:
            args = dict(flight_id=obj.id, seats=quantity or 1, stay_id=None, nights=None, guide_id=None, guide_days=None)
        else:
            # A stay or guide alone needs dates: use the next flight to that country (flight + item).
            flights = self.call("search_flights", from_city="Beirut", to_country=obj.country.name, month=None, date=None).data["flights"]
            if not flights:
                return f"There are no upcoming flights to {obj.country.name} to build a trip around."
            f = flights[0]
            args = dict(flight_id=f["flight_id"], seats=1,
                        stay_id=obj.id if model is Stay else None, nights=quantity or f["nights"] if model is Stay else None,
                        guide_id=obj.id if model is GuideProfile else None, guide_days=quantity or 2 if model is GuideProfile else None)
        self.cards = []
        result = self.call("create_booking", start_date=None, end_date=None, **args)
        if result.is_error:
            return f"I couldn't prepare that booking: {result.data['error']}"
        extra = "" if model is Flight else " I added the next flight from Beirut so the trip has dates."
        return f"Here's your booking summary.{extra} Click **Confirm** (or type \"confirm\") to book it."
