"""The trip basket: what a traveler has picked but not paid for yet.

It lives in the Flask session (the signed cookie), like a shopping cart.
We store only ids and quantities, never prices: prices are always read
fresh from the database, so nobody can change a price in their cookie.

    session["basket"] = {
        "country_id": 1,
        "flight": [flight_id, seats] or None,
        "stay":   [stay_id, nights]  or None,
        "guide":  [guide_id, days]   or None,
        "start": "2027-03-12" or None,   # trip dates, only used when there is no flight
        "end":   "2027-03-19" or None,
    }
"""
from datetime import date

from flask import session

from extensions import db
from models import Country, Flight, GuideProfile, Stay
from services.pricing import estimate_trip_cost

MODELS = {"flight": Flight, "stay": Stay, "guide": GuideProfile}
EMPTY = {"country_id": None, "flight": None, "stay": None, "guide": None, "start": None, "end": None}


def get_raw():
    return {**EMPTY, **session.get("basket", {})}


def save_raw(basket):
    session["basket"] = basket


def clear():
    session.pop("basket", None)


def count():
    basket = get_raw()
    return sum(1 for key in MODELS if basket[key])


def add(item_type, obj, quantity):
    """Put a flight/stay/guide in the basket. Returns True if the basket was
    emptied first because the item is in a different country."""
    basket = get_raw()
    switched = basket["country_id"] not in (None, obj.country_id)
    if switched:
        basket = dict(EMPTY)
    basket["country_id"] = obj.country_id
    basket[item_type] = [obj.id, quantity]
    if item_type == "flight":  # a flight fixes the trip dates
        basket["start"] = basket["end"] = None
    save_raw(basket)
    return switched


def remove(item_type):
    basket = get_raw()
    basket[item_type] = None
    if not any(basket[key] for key in MODELS):
        basket = dict(EMPTY)
    save_raw(basket)


def details():
    """Load the basket's objects from the database and work out dates + prices.

    Returns a dict for the templates, or None when the basket is empty.
    Items that disappeared (deleted by the admin, guide no longer approved)
    are dropped silently.
    """
    basket = get_raw()
    country = db.session.get(Country, basket["country_id"]) if basket["country_id"] else None
    if country is None:
        return None

    loaded = {}
    for item_type, model in MODELS.items():
        if basket[item_type]:
            obj_id, quantity = basket[item_type]
            obj = db.session.get(model, obj_id)
            if obj is None or obj.country_id != country.id:
                continue
            if item_type == "guide" and obj.status != "approved":
                continue
            loaded[item_type] = (obj, quantity)
    if not loaded:
        return None

    # Trip dates: from the flight if there is one, otherwise chosen by the traveler.
    flight = loaded.get("flight", (None, 0))[0]
    if flight:
        start, end, dates_fixed = flight.depart_date, flight.return_date, True
    else:
        start = _parse_date(basket["start"])
        end = _parse_date(basket["end"])
        dates_fixed = False

    estimate = estimate_trip_cost(
        flight=flight, travelers=loaded.get("flight", (None, 1))[1],
        stay=loaded.get("stay", (None, 0))[0], nights=loaded.get("stay", (None, 0))[1],
        guide=loaded.get("guide", (None, 0))[0], guide_days=loaded.get("guide", (None, 0))[1],
    )
    return {
        "country": country,
        "items": loaded,
        "start": start,
        "end": end,
        "dates_fixed": dates_fixed,
        "estimate": estimate,
        # The format create_booking() expects:
        "booking_items": [{"type": t, "id": obj.id, "quantity": q} for t, (obj, q) in loaded.items()],
    }


def set_dates(start_text, end_text):
    basket = get_raw()
    basket["start"], basket["end"] = start_text, end_text
    save_raw(basket)


def _parse_date(text):
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None
