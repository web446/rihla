"""Describes the 5 content tables the admin can manage (countries, monuments,
restaurants, stays, flights).

Instead of writing 5 almost identical sets of pages, each table is DESCRIBED
here once (its fields and its list columns). The admin routes and the two
templates (admin/list.html and admin/form.html) then work for all of them.
Adding a new manageable table = adding one entry to RESOURCES.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from extensions import db
from models import ENTRY_TYPES, BookingItem, Country, Flight, GuideProfile, Monument, Restaurant, Stay
from services.pricing import dollars_to_cents, format_money


@dataclass
class Field:
    name: str                 # model attribute, e.g. "price_cents"
    label: str                # shown in the form
    kind: str = "text"        # text, textarea, money, int, float, date, choice, country, url, months, slug
    required: bool = True
    max_length: int = 150
    min: float = None         # for money (in dollars), int and float
    max: float = None
    choices: tuple = ()
    help: str = ""


@dataclass
class Resource:
    key: str                  # used in URLs: /admin/content/flights
    model: type
    title: str                # "Flights"
    singular: str             # "flight"
    fields: list
    columns: list             # [(label, function(obj) -> text)]
    order_by: object = None
    has_country: bool = True  # child tables can be filtered by country
    extra_check: object = None  # function(cleaned, obj) -> {field: error}


# ---------------------------------------------------------------------------
# Extra rules that involve more than one field
# ---------------------------------------------------------------------------
def check_country(cleaned, obj):
    errors = {}
    for attr in ("name", "slug"):
        taken = db.session.execute(
            db.select(Country.id).where(getattr(Country, attr) == cleaned[attr], Country.id != (obj.id if obj else 0))
        ).first()
        if taken:
            errors[attr] = f"Another country already uses this {attr}."
    return errors


def check_flight(cleaned, obj):
    errors = {}
    if cleaned["return_date"] and cleaned["depart_date"] and cleaned["return_date"] < cleaned["depart_date"]:
        errors["return_date"] = "The return must be on or after the departure."
    if obj is not None:  # editing: the plane can't shrink below the seats already sold
        sold = obj.seats_total - obj.seats_available
        if cleaned["seats_total"] < sold:
            errors["seats_total"] = f"{sold} seats are already booked on this flight."
    return errors


RESOURCES = {
    "countries": Resource(
        key="countries", model=Country, title="Countries", singular="country", has_country=False,
        order_by=Country.name, extra_check=check_country,
        fields=[
            Field("name", "Name", max_length=80),
            Field("slug", "URL name", kind="slug", max_length=80, help="Lowercase letters and dashes, e.g. south-korea"),
            Field("tagline", "Tagline", required=False),
            Field("description", "Description", kind="textarea", max_length=2000),
            Field("best_time", "Best time to visit", max_length=100),
            Field("currency", "Currency", max_length=50),
            Field("language", "Language", max_length=50),
            Field("warm_months", "Warm months", kind="months", required=False, help="Month numbers, e.g. 4,5,6,9"),
            Field("tags", "Interests", required=False, help="Comma separated, e.g. beach,food,history"),
            Field("avg_daily_spend_cents", "Daily spend per person ($)", kind="money", min=0, max=2000),
            Field("hero_image", "Photo URL", kind="url", required=False, max_length=500,
                  help="Real photo, e.g. from Wikimedia Commons (https://upload.wikimedia.org/...)"),
            Field("hero_credit", "Photo credit", required=False, max_length=300, help='"Author · CC BY-SA 4.0"'),
            Field("hero_source", "Photo source page", kind="url", required=False, max_length=500),
            # Entry rules for a Lebanese passport
            Field("entry_type", "Entry with a Lebanese passport", kind="choice", choices=ENTRY_TYPES,
                  help="visa_free, visa_on_arrival, conditional or evisa"),
            Field("max_stay", "Maximum stay", max_length=60, help='e.g. "90 days in any 180"'),
            Field("entry_notes", "Entry conditions", kind="textarea", required=False, max_length=1000),
            Field("popularity", "Popularity with Lebanese (1-5)", kind="int", min=1, max=5),
            Field("popularity_note", "Popularity note", required=False, max_length=200),
        ],
        columns=[("Name", lambda c: c.name), ("Entry", lambda c: f"{c.entry_label} · {c.max_stay}"),
                 ("Popularity", lambda c: "●" * c.popularity),
                 ("Daily spend", lambda c: format_money(c.avg_daily_spend_cents)),
                 ("Content", lambda c: f"{len(c.monuments)} sights · {len(c.restaurants)} food · {len(c.stays)} stays · {len(c.flights)} flights")],
    ),
    "monuments": Resource(
        key="monuments", model=Monument, title="Monuments", singular="monument", order_by=Monument.name,
        fields=[
            Field("country_id", "Country", kind="country"),
            Field("name", "Name", max_length=120),
            Field("city", "City", max_length=80),
            Field("entry_cost_cents", "Entry cost ($)", kind="money", min=0, max=1000, help="0 = free"),
            Field("description", "Description", kind="textarea", max_length=1000),
            Field("image", "Photo URL", kind="url", required=False, max_length=500),
            Field("image_credit", "Photo credit", required=False, max_length=300, help='"Author · CC BY-SA 4.0"'),
            Field("image_source", "Photo source page", kind="url", required=False, max_length=500),
        ],
        columns=[("Name", lambda m: m.name), ("Country", lambda m: m.country.name), ("City", lambda m: m.city),
                 ("Entry", lambda m: "Free" if m.entry_cost_cents == 0 else format_money(m.entry_cost_cents))],
    ),
    "restaurants": Resource(
        key="restaurants", model=Restaurant, title="Restaurants", singular="restaurant", order_by=Restaurant.name,
        fields=[
            Field("country_id", "Country", kind="country"),
            Field("name", "Name", max_length=120),
            Field("city", "City", max_length=80),
            Field("must_try_dish", "Must-try dish", max_length=120),
            Field("price_range", "Price range", kind="choice", choices=("$", "$$", "$$$")),
            Field("avg_meal_cost_cents", "Average meal ($)", kind="money", min=0.5, max=1000),
            Field("description", "Description", kind="textarea", max_length=1000),
            Field("image", "Photo URL", kind="url", required=False, max_length=255),
        ],
        columns=[("Name", lambda r: r.name), ("Country", lambda r: r.country.name), ("Dish", lambda r: r.must_try_dish),
                 ("Price", lambda r: f"{r.price_range} · {format_money(r.avg_meal_cost_cents)}")],
    ),
    "stays": Resource(
        key="stays", model=Stay, title="Stays", singular="stay", order_by=Stay.name,
        fields=[
            Field("country_id", "Country", kind="country"),
            Field("name", "Name", max_length=120),
            Field("type", "Type", kind="choice", choices=("hotel", "apartment")),
            Field("city", "City", max_length=80),
            Field("price_per_night_cents", "Price per night ($)", kind="money", min=1, max=10000),
            Field("rating", "Rating (0-5)", kind="float", min=0, max=5),
            Field("description", "Description", kind="textarea", max_length=1000),
            Field("image", "Photo URL", kind="url", required=False, max_length=255),
        ],
        columns=[("Name", lambda s: s.name), ("Country", lambda s: s.country.name), ("Type", lambda s: s.type),
                 ("Per night", lambda s: format_money(s.price_per_night_cents)), ("Rating", lambda s: f"★ {s.rating}")],
    ),
    "flights": Resource(
        key="flights", model=Flight, title="Flights", singular="flight", order_by=Flight.depart_date,
        extra_check=check_flight,
        fields=[
            Field("country_id", "Destination country", kind="country"),
            Field("airline", "Airline", max_length=60),
            Field("flight_number", "Flight number", max_length=12),
            Field("to_city", "Arrival city", max_length=60),
            Field("stops", "Stops", max_length=60, help='Start with "Direct" for non-stop (e.g. "Direct (charter)"), or "via Doha"'),
            Field("depart_date", "Departure date", kind="date"),
            Field("return_date", "Return date", kind="date"),
            Field("price_cents", "Price per seat, round trip ($)", kind="money", min=1, max=20000),
            Field("seats_total", "Seats on the plane", kind="int", min=1, max=600),
        ],
        columns=[("Flight", lambda f: f"{f.airline} {f.flight_number}"), ("To", lambda f: f"{f.to_city}, {f.country.name}"),
                 ("Dates", lambda f: f"{f.depart_date:%d %b %Y} → {f.return_date:%d %b}"),
                 ("Price", lambda f: format_money(f.price_cents)), ("Seats", lambda f: f"{f.seats_available} / {f.seats_total}")],
    ),
}


# ---------------------------------------------------------------------------
# Generic form reading / validation
# ---------------------------------------------------------------------------
def read_form(resource, form, country_ids):
    """Check every field of `resource`. Returns (errors, cleaned, raw).

    raw     = what was typed (to show it again in the form if there are errors)
    cleaned = converted values ready for the model (cents, ints, dates...)
    """
    errors, cleaned, raw = {}, {}, {}
    for f in resource.fields:
        text = (form.get(f.name) or "").strip()
        raw[f.name] = text
        if not text:
            if f.required:
                errors[f.name] = "This field is required."
            cleaned[f.name] = None
            continue
        value, error = _convert(f, text, country_ids)
        if error:
            errors[f.name] = error
        cleaned[f.name] = value
    return errors, cleaned, raw


def _convert(f, text, country_ids):
    """Turn the typed text into the right Python value. Returns (value, error)."""
    if f.kind in ("text", "textarea"):
        return (text, None) if len(text) <= f.max_length else (None, f"Maximum {f.max_length} characters.")
    if f.kind == "slug":
        return (text, None) if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", text) else (None, "Use lowercase letters, numbers and dashes.")
    if f.kind == "url":
        return (text, None) if re.fullmatch(r"https://\S+", text) and len(text) <= f.max_length else (None, "Use a full https:// link.")
    if f.kind == "money":
        cents = dollars_to_cents(text)
        if cents is None or not f.min * 100 <= cents <= f.max * 100:
            return None, f"Enter an amount between ${f.min:g} and ${f.max:,g}."
        return cents, None
    if f.kind in ("int", "float"):
        try:
            number = int(text) if f.kind == "int" else float(text)
        except ValueError:
            return None, "Enter a number."
        return (number, None) if f.min <= number <= f.max else (None, f"Between {f.min:g} and {f.max:g}.")
    if f.kind == "date":
        try:
            return date.fromisoformat(text), None
        except ValueError:
            return None, "Enter a valid date."
    if f.kind == "choice":
        return (text, None) if text in f.choices else (None, "Choose one of the options.")
    if f.kind == "country":
        try:
            country_id = int(text)
        except ValueError:
            country_id = None
        return (country_id, None) if country_id in country_ids else (None, "Choose a country.")
    if f.kind == "months":
        try:
            months = sorted({int(m) for m in text.split(",") if m.strip()})
        except ValueError:
            return None, "Use month numbers separated by commas."
        if not all(1 <= m <= 12 for m in months):
            return None, "Months go from 1 to 12."
        return ",".join(map(str, months)), None
    return text, None


def form_values(resource, obj):
    """The current values of `obj`, as text for the edit form (cents -> dollars, dates -> ISO)."""
    values = {}
    for f in resource.fields:
        value = getattr(obj, f.name)
        if value is None:
            values[f.name] = ""
        elif f.kind == "money":
            values[f.name] = f"{value / 100:.2f}"
        elif f.kind == "date":
            values[f.name] = value.isoformat()
        else:
            values[f.name] = str(value)
    return values


def delete_problem(resource, obj):
    """Why this row can't be deleted (it's used by bookings or guides), or None.

    We check first to show a friendly message; the database's foreign keys
    would refuse the delete anyway.
    """
    def used(condition):
        return db.session.execute(db.select(BookingItem.id).where(condition).limit(1)).first() is not None

    if resource.key == "flights" and used(BookingItem.flight_id == obj.id):
        return "This flight has bookings, so it can't be deleted."
    if resource.key == "stays" and used(BookingItem.stay_id == obj.id):
        return "This stay has bookings, so it can't be deleted."
    if resource.key == "countries":
        if db.session.execute(db.select(GuideProfile.id).where(GuideProfile.country_id == obj.id).limit(1)).first():
            return "Guides work in this country, so it can't be deleted."
        if any(used(BookingItem.flight_id == f.id) for f in obj.flights) or any(used(BookingItem.stay_id == s.id) for s in obj.stays):
            return "This country has booked flights or stays, so it can't be deleted."
    return None
