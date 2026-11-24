"""The 9 tools of the AI travel agent.

Each tool is:
  1. a JSON schema in TOOLS (what Claude is told it can call), and
  2. a Python function in HANDLERS that answers ONLY from our database,
     by calling the same services/ functions the website uses.

run_tool() is the single entry point, used by BOTH the Claude agent and the
demo agent. The user is ALWAYS passed in by our server from the session:
it is never a tool argument, so the AI can't act for somebody else.

Every handler returns a ToolResult:
  data  -> sent back to Claude as the tool result (JSON)
  cards -> small flight / hotel / guide / summary cards shown in the chat
"""
import json
from dataclasses import dataclass, field
from datetime import date

from extensions import db
from models import Booking, Flight, GuideProfile, Stay
from services import search
from services.booking import BookingError, preview_booking
from services.pricing import estimate_trip_cost, format_money

from agent import proposals


@dataclass
class ToolResult:
    data: dict
    cards: list = field(default_factory=list)
    is_error: bool = False


class ToolInputError(Exception):
    """Bad arguments from the model: sent back as an error result so it can retry."""


# ---------------------------------------------------------------------------
# Schemas. strict=True makes the API guarantee the arguments match the schema.
# Strict mode needs every property listed in "required" and
# additionalProperties: false, so "optional" values are written as
# "string or null" (the model sends null when it has no value).
# ---------------------------------------------------------------------------
def _opt(json_type, description):
    return {"anyOf": [{"type": json_type}, {"type": "null"}], "description": description}


def _tool(name, description, properties):
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {"type": "object", "properties": properties,
                         "required": list(properties), "additionalProperties": False},
    }


TOOLS = [
    _tool("search_countries",
          "Find destinations that match the traveler's wishes, each with an estimated trip price and the entry "
          "rules for a Lebanese passport. Call this whenever the traveler hasn't chosen a country yet "
          "(e.g. 'somewhere warm in March') or asks where they can go without a visa.",
          {"no_visa_in_advance_only": {"anyOf": [{"type": "boolean"}, {"type": "null"}],
                                       "description": "true = only countries a Lebanese passport can enter "
                                                      "visa-free or with a visa on arrival"},
           "month": _opt("integer", "Travel month, 1-12"),
           "max_budget_usd": _opt("number", "Maximum total budget in US dollars"),
           "days": _opt("integer", "Trip length in days (default 7)"),
           "interests": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                         "description": "Interests such as beach, food, history, culture, nature, city, islands, desert, art"},
           "travelers": _opt("integer", "Number of travelers (default 1)")}),
    _tool("get_country_details",
          "Overview of one country: entry rules for a Lebanese passport (visa, max stay, conditions), description, "
          "best time, currency, monuments with prices, food, cheapest stays. "
          "Call this when the traveler asks about a specific country.",
          {"country": {"type": "string", "description": "Country name, e.g. 'Italy'"}}),
    _tool("search_flights",
          "Upcoming round-trip flights that still have seats. Call this before proposing any flight.",
          {"from_city": {"type": "string", "description": "Departure city. Only 'Beirut' is served."},
           "to_country": {"type": "string", "description": "Destination country name"},
           "month": _opt("integer", "Departure month 1-12"),
           "date": _opt("string", "Earliest departure date, YYYY-MM-DD")}),
    _tool("search_hotels",
          "Hotels and apartments in a country, cheapest first, with the total for the given nights.",
          {"country": {"type": "string", "description": "Country name"},
           "nights": _opt("integer", "Number of nights, to show a total price"),
           "max_price_per_night_usd": _opt("number", "Budget per night in US dollars"),
           "type": {"anyOf": [{"type": "string", "enum": ["hotel", "apartment"]}, {"type": "null"}],
                    "description": "Only hotels or only apartments"}}),
    _tool("list_guides",
          "Approved local guides in a country with their rating, languages and daily price.",
          {"country": {"type": "string", "description": "Country name"},
           "language": _opt("string", "A language the guide must speak"),
           "max_price_per_day_usd": _opt("number", "Budget per day in US dollars")}),
    _tool("estimate_trip_cost",
          "Exact price breakdown for chosen items, including typical food and transport spending. "
          "Use the ids returned by the search tools.",
          {"country": {"type": "string", "description": "Country name"},
           "flight_id": _opt("integer", "Flight id"),
           "stay_id": _opt("integer", "Stay id"),
           "nights": _opt("integer", "Nights at the stay"),
           "guide_id": _opt("integer", "Guide id"),
           "guide_days": _opt("integer", "Days with the guide"),
           "travelers": _opt("integer", "Number of travelers (seats)"),
           "days": _opt("integer", "Trip length in days")}),
    _tool("create_booking",
          "PREPARE a booking for the traveler to confirm. This does NOT book anything: it shows the traveler a "
          "summary with a Confirm button. Call it only when the traveler has agreed on the items. Trip dates come "
          "from the flight; without a flight, give start_date and end_date.",
          {"flight_id": _opt("integer", "Flight id"),
           "seats": _opt("integer", "Number of seats (default 1)"),
           "stay_id": _opt("integer", "Stay id"),
           "nights": _opt("integer", "Nights at the stay"),
           "guide_id": _opt("integer", "Guide id"),
           "guide_days": _opt("integer", "Days with the guide"),
           "start_date": _opt("string", "Trip start YYYY-MM-DD (only without a flight)"),
           "end_date": _opt("string", "Trip end YYYY-MM-DD (only without a flight)")}),
    _tool("list_my_bookings",
          "The logged-in traveler's own bookings (upcoming, past and cancelled). Call this for 'my trips' questions.",
          {}),
    _tool("cancel_booking",
          "PREPARE the cancellation of one of the traveler's upcoming bookings. Nothing is cancelled until the "
          "traveler clicks Confirm.",
          {"booking_id": {"type": "integer", "description": "The trip number, e.g. 12"}}),
]


# ---------------------------------------------------------------------------
# Input helpers: the tools re-check everything (never trust tool arguments)
# ---------------------------------------------------------------------------
def _country(name):
    country = search.get_country(name or "")
    if country is None:
        known = ", ".join(c.name for c in search.all_countries())
        raise ToolInputError(f"Unknown country '{name}'. We offer: {known}.")
    return country


def _int(value, low, high, name, default=None):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value or not low <= value <= high:
        raise ToolInputError(f"{name} must be a whole number between {low} and {high}.")
    return int(value)


def _usd(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ToolInputError(f"{name} must be a positive amount in dollars.")
    return int(round(value * 100))


def _date(value, name):
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolInputError(f"{name} must be a date like 2027-03-15.")


def _get(model, item_id, country=None):
    obj = db.session.get(model, item_id) if item_id is not None else None
    if item_id is not None and (obj is None or (country is not None and obj.country_id != country.id)):
        raise ToolInputError(f"No {model.__name__.lower()} with id {item_id}" + (f" in {country.name}." if country else "."))
    if isinstance(obj, GuideProfile) and obj.status != "approved":
        raise ToolInputError(f"Guide {item_id} is not available.")
    return obj


# ---------------------------------------------------------------------------
# Cards (what the chat window draws). Money is already formatted here.
# ---------------------------------------------------------------------------
def entry_info(c):
    """Entry rules for a Lebanese passport, as sent to the AI."""
    return {"entry_for_lebanese_passport": c.entry_label, "max_stay": c.max_stay,
            "entry_conditions": c.entry_notes or None, "no_visa_in_advance": c.no_visa_in_advance,
            "direct_flight_from_beirut": c.has_direct_flight(),
            "popularity_with_lebanese_1_to_5": c.popularity, "popularity_note": c.popularity_note or None}


def country_card(c, price):
    return {"type": "country", "title": c.name, "slug": c.slug, "subtitle": c.tagline, "price": price,
            "entry": f"🇱🇧 {c.entry_label} · {c.max_stay}", "direct": c.has_direct_flight(), "warm": None}


def flight_card(f):
    return {"type": "flight", "id": f.id, "title": f"{f.airline} {f.flight_number}", "route": f"Beirut → {f.to_city}",
            "dates": f"{f.depart_date:%a %d %b} → {f.return_date:%a %d %b %Y}", "stops": f.stops,
            "price": format_money(f.price_cents), "seats": f.seats_available, "country": f.country.name}


def stay_card(s, nights=None):
    card = {"type": "stay", "id": s.id, "title": s.name, "subtitle": f"{s.type.capitalize()} · {s.city}",
            "price": f"{format_money(s.price_per_night_cents)} / night", "rating": s.rating, "country": s.country.name}
    if nights:
        card["total"] = f"{format_money(s.price_per_night_cents * nights)} for {nights} nights"
    return card


def guide_card(g, rating, count):
    return {"type": "guide", "id": g.id, "title": g.user.full_name, "subtitle": g.languages,
            "price": f"{format_money(g.price_per_day_cents)} / day", "rating": rating, "reviews": count,
            "country": g.country.name}


# ---------------------------------------------------------------------------
# The tool functions
# ---------------------------------------------------------------------------
def search_countries(args, user, conversation_id):
    month = _int(args.get("month"), 1, 12, "month")
    days = _int(args.get("days"), 1, 30, "days", default=7)
    travelers = _int(args.get("travelers"), 1, 9, "travelers", default=1)
    results = search.search_countries(month=month, max_budget_cents=_usd(args.get("max_budget_usd"), "max_budget_usd"),
                                      days=days, interests=args.get("interests") or None, travelers=travelers,
                                      no_visa_only=bool(args.get("no_visa_in_advance_only")))
    data, cards = [], []
    for r in results[:6]:
        c, est = r["country"], r["estimate"]
        data.append({"country": c.name, "warm_that_month": r["warm"], "estimated_total_usd": est["total_cents"] / 100,
                     "estimate_includes": [line["label"] for line in est["lines"]],
                     "cheapest_flight": ({"flight_id": r["flight"].id, "depart": r["flight"].depart_date.isoformat(),
                                          "price_usd": r["flight"].price_cents / 100} if r["flight"] else None),
                     "interests": c.tag_list(), **entry_info(c)})
        card = country_card(c, f"≈ {format_money(est['total_cents'])} for {days} days")
        card["warm"] = r["warm"]
        cards.append(card)
    return ToolResult({"days": days, "travelers": travelers, "results": data,
                       "note": "Estimates = cheapest flight + cheapest stay + daily spending."}, cards)


def get_country_details(args, user, conversation_id):
    c = _country(args.get("country"))
    stays = search.search_stays(c)[:3]
    return ToolResult({
        "country": c.name, **entry_info(c),
        "description": c.description, "best_time": c.best_time, "currency": c.currency,
        "language": c.language, "warm_months": c.warm_month_list(), "interests": c.tag_list(),
        "daily_spend_usd": c.avg_daily_spend_cents / 100,
        "monuments": [{"name": m.name, "city": m.city, "entry_usd": m.entry_cost_cents / 100} for m in c.monuments],
        "food": [{"restaurant": r.name, "city": r.city, "must_try": r.must_try_dish, "price_range": r.price_range}
                 for r in c.restaurants],
        "cheapest_stays": [{"stay_id": s.id, "name": s.name, "per_night_usd": s.price_per_night_cents / 100} for s in stays],
        "upcoming_flights": len(search.upcoming_flights(c)),
        "approved_guides": len(search.guides_with_ratings(c)),
    }, [country_card(c, f"Best time: {c.best_time}")])


def search_flights(args, user, conversation_id):
    if (args.get("from_city") or "Beirut").strip().lower() not in ("beirut", "bey"):
        raise ToolInputError("Rihla only sells flights departing from Beirut.")
    c = _country(args.get("to_country"))
    flights = search.upcoming_flights(c, month=_int(args.get("month"), 1, 12, "month"),
                                      on_or_after=_date(args.get("date"), "date"))
    data = [{"flight_id": f.id, "airline": f.airline, "flight_number": f.flight_number, "to_city": f.to_city,
             "stops": f.stops, "depart": f.depart_date.isoformat(), "return": f.return_date.isoformat(),
             "nights": (f.return_date - f.depart_date).days, "price_per_seat_usd": f.price_cents / 100,
             "seats_left": f.seats_available} for f in flights[:6]]
    return ToolResult({"country": c.name, "flights": data,
                       "note": None if data else "No upcoming flights match. Try another month."},
                      [flight_card(f) for f in flights[:6]])


def search_hotels(args, user, conversation_id):
    c = _country(args.get("country"))
    nights = _int(args.get("nights"), 1, 30, "nights")
    stays = search.search_stays(c, max_price_cents=_usd(args.get("max_price_per_night_usd"), "max_price_per_night_usd"),
                                stay_type=args.get("type"))
    data = [{"stay_id": s.id, "name": s.name, "type": s.type, "city": s.city, "rating": s.rating,
             "per_night_usd": s.price_per_night_cents / 100,
             "total_usd": s.price_per_night_cents * nights / 100 if nights else None} for s in stays[:6]]
    return ToolResult({"country": c.name, "stays": data}, [stay_card(s, nights) for s in stays[:6]])


def list_guides(args, user, conversation_id):
    c = _country(args.get("country"))
    guides = search.guides_with_ratings(c, language=args.get("language"),
                                        max_price_cents=_usd(args.get("max_price_per_day_usd"), "max_price_per_day_usd"))
    data = [{"guide_id": g.id, "name": g.user.full_name, "languages": g.language_list(), "rating": r,
             "reviews": n, "per_day_usd": g.price_per_day_cents / 100, "bio": g.bio} for g, r, n in guides]
    return ToolResult({"country": c.name, "guides": data}, [guide_card(g, r, n) for g, r, n in guides])


def estimate_trip_cost_tool(args, user, conversation_id):
    c = _country(args.get("country"))
    flight = _get(Flight, args.get("flight_id"), c)
    nights = _int(args.get("nights"), 0, 30, "nights",
                  default=(flight.return_date - flight.depart_date).days if flight else 0)
    estimate = estimate_trip_cost(
        country=c, flight=flight, stay=_get(Stay, args.get("stay_id"), c), nights=nights,
        guide=_get(GuideProfile, args.get("guide_id"), c), guide_days=_int(args.get("guide_days"), 0, 14, "guide_days", default=0),
        travelers=_int(args.get("travelers"), 1, 9, "travelers", default=1),
        days=_int(args.get("days"), 0, 30, "days", default=nights + 1 if nights else 0))
    return ToolResult({"lines": [{"item": l["label"], "detail": l["detail"], "usd": l["total_cents"] / 100}
                                 for l in estimate["lines"]],
                       "total_usd": estimate["total_cents"] / 100})


def create_booking_tool(args, user, conversation_id):
    """Prepares a proposal. Uses preview_booking(): the SAME rules as a real booking."""
    items = []
    flight = _get(Flight, args.get("flight_id"))
    if flight:
        items.append({"type": "flight", "id": flight.id, "quantity": _int(args.get("seats"), 1, 9, "seats", default=1)})
    if args.get("stay_id") is not None:
        stay = _get(Stay, args["stay_id"])
        default_nights = (flight.return_date - flight.depart_date).days if flight else None
        nights = _int(args.get("nights"), 1, 30, "nights", default=default_nights)
        if nights is None:
            raise ToolInputError("Give the number of nights for the stay.")
        items.append({"type": "stay", "id": stay.id, "quantity": nights})
    if args.get("guide_id") is not None:
        guide = _get(GuideProfile, args["guide_id"])
        items.append({"type": "guide", "id": guide.id, "quantity": _int(args.get("guide_days"), 1, 14, "guide_days", default=1)})
    if not items:
        raise ToolInputError("Choose at least a flight, a stay or a guide.")

    if flight:
        start, end = flight.depart_date, flight.return_date
    else:
        start, end = _date(args.get("start_date"), "start_date"), _date(args.get("end_date"), "end_date")
        if not start or not end:
            raise ToolInputError("Without a flight, give start_date and end_date.")

    try:
        preview = preview_booking(items, start, end)
    except BookingError as error:
        raise ToolInputError(str(error))

    from services.basket import MODELS  # flight / stay / guide model classes
    lines = []
    for line in preview["lines"]:
        obj = db.session.get(MODELS[line["type"]], line["id"])
        unit = {"flight": "seat(s)", "stay": "night(s)", "guide": "day(s)"}[line["type"]]
        name = {"flight": lambda o: f"✈ {o.airline} {o.flight_number}, Beirut → {o.to_city}",
                "stay": lambda o: f"🛏 {o.name}, {o.city}",
                "guide": lambda o: f"🧭 Guide {o.user.full_name}"}[line["type"]](obj)
        lines.append({"label": name, "detail": f"{line['quantity']} {unit} × {format_money(line['unit_cents'])}",
                      "total": format_money(line["total_cents"])})

    proposal = proposals.save_proposal(user, conversation_id, "create",
                                       {"items": items, "start": start.isoformat(), "end": end.isoformat()},
                                       preview["total_cents"])
    card = {"type": "summary", "proposal_id": proposal.id, "action": "create",
            "title": f"Trip to {preview['country'].name}", "dates": f"{start:%a %d %b} → {end:%a %d %b %Y}",
            "lines": lines, "total": format_money(preview["total_cents"])}
    return ToolResult({"status": "WAITING_FOR_USER_CONFIRMATION", "proposal_id": proposal.id,
                       "total_usd": preview["total_cents"] / 100, "start": start.isoformat(), "end": end.isoformat(),
                       "instruction": "Nothing is booked yet. Show the summary and ask the traveler to click Confirm "
                                      "or type 'confirm'. Never say it is booked."}, [card])


def list_my_bookings(args, user, conversation_id):
    bookings = db.session.execute(
        db.select(Booking).where(Booking.traveler_id == user.id).order_by(Booking.start_date)   # ONLY this user
    ).scalars().all()
    today = date.today()
    data = [{"trip_number": b.id, "country": b.country.name if b.country else None, "start": b.start_date.isoformat(),
             "end": b.end_date.isoformat(), "total_usd": b.total_cents / 100,
             "status": b.status if b.status == "cancelled" else ("upcoming" if b.start_date > today else "past"),
             "items": [item.title for item in b.items], "booked_with_ai": b.source == "agent"} for b in bookings]
    return ToolResult({"bookings": data}, [proposals.booking_card(b) for b in bookings])


def cancel_booking_tool(args, user, conversation_id):
    booking_id = _int(args.get("booking_id"), 1, 10**9, "booking_id")
    booking = db.session.get(Booking, booking_id)
    if booking is None or booking.traveler_id != user.id:      # someone else's trip = "not found"
        raise ToolInputError(f"You have no trip #{booking_id}.")
    if booking.status != "confirmed":
        raise ToolInputError(f"Trip #{booking_id} is already cancelled.")
    if booking.start_date <= date.today():
        raise ToolInputError(f"Trip #{booking_id} has already started, so it can't be cancelled.")
    proposal = proposals.save_proposal(user, conversation_id, "cancel", {"booking_id": booking.id}, booking.total_cents)
    card = {"type": "summary", "proposal_id": proposal.id, "action": "cancel",
            "title": f"Cancel trip #{booking.id} to {booking.country.name}",
            "dates": f"{booking.start_date:%a %d %b} → {booking.end_date:%a %d %b %Y}",
            "lines": [{"label": item.title, "detail": f"{item.quantity} {item.unit}",
                       "total": format_money(item.line_total_cents)} for item in booking.items],
            "total": format_money(booking.total_cents)}
    return ToolResult({"status": "WAITING_FOR_USER_CONFIRMATION", "proposal_id": proposal.id,
                       "instruction": "Nothing is cancelled yet. Ask the traveler to click Confirm or type 'confirm'."},
                      [card])


HANDLERS = {
    "search_countries": search_countries,
    "get_country_details": get_country_details,
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "list_guides": list_guides,
    "estimate_trip_cost": estimate_trip_cost_tool,
    "create_booking": create_booking_tool,
    "list_my_bookings": list_my_bookings,
    "cancel_booking": cancel_booking_tool,
}


def run_tool(name, args, user, conversation_id):
    """Run one tool for the logged-in `user`. Never raises: errors become error results."""
    handler = HANDLERS.get(name)
    if handler is None:
        return ToolResult({"error": f"Unknown tool {name}"}, is_error=True)
    if not isinstance(args, dict):
        return ToolResult({"error": "Tool input must be an object."}, is_error=True)
    try:
        return handler(args, user, conversation_id)
    except ToolInputError as error:
        db.session.rollback()
        return ToolResult({"error": str(error)}, is_error=True)


def result_to_json(result):
    """The tool result text Claude reads (compact JSON)."""
    return json.dumps(result.data, ensure_ascii=False, default=str)
