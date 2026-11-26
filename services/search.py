"""Read-only queries: finding countries, flights, stays and guides.

Used by the public pages (homepage search, countries list, country pages)
and the admin pages, so every page sees the same data and the same rules.
"""
import calendar
from datetime import date

from sqlalchemy import func

from extensions import db
from models import Country, Flight, GuideProfile, Review, Stay
from services.pricing import estimate_trip_cost

MONTH_NAMES = {i: calendar.month_name[i] for i in range(1, 13)}  # {1: "January", ...}


def all_countries():
    return db.session.execute(db.select(Country).order_by(Country.name)).scalars().all()


def get_country(slug_or_name):
    """Find a country by slug ("italy") or name ("Italy"), ignoring upper/lower case."""
    key = (slug_or_name or "").strip().lower()
    return db.session.execute(
        db.select(Country).where((Country.slug == key) | (func.lower(Country.name) == key))
    ).scalar_one_or_none()


def all_interests():
    """Every tag used by at least one country, e.g. ["beach", "culture", ...]."""
    return sorted({tag for country in all_countries() for tag in country.tag_list()})


# ---------------------------------------------------------------------------
# Flights and stays
# ---------------------------------------------------------------------------
def upcoming_flights(country, month=None, on_or_after=None):
    """Future flights to a country that still have seats, earliest first."""
    query = db.select(Flight).where(
        Flight.country_id == country.id,
        Flight.seats_available > 0,
        Flight.depart_date >= (on_or_after or date.today()),
    )
    flights = db.session.execute(query.order_by(Flight.depart_date)).scalars().all()
    if month:
        flights = [f for f in flights if f.depart_date.month == month]
    return flights


def cheapest_flight(country, month=None):
    flights = upcoming_flights(country, month)
    return min(flights, key=lambda f: f.price_cents) if flights else None


def search_stays(country, max_price_cents=None, stay_type=None):
    query = db.select(Stay).where(Stay.country_id == country.id)
    if max_price_cents:
        query = query.where(Stay.price_per_night_cents <= max_price_cents)
    if stay_type in ("hotel", "apartment"):
        query = query.where(Stay.type == stay_type)
    return db.session.execute(query.order_by(Stay.price_per_night_cents)).scalars().all()


# ---------------------------------------------------------------------------
# Guides (only APPROVED guides are ever shown to travelers)
# ---------------------------------------------------------------------------
def guides_with_ratings(country=None, language=None, max_price_cents=None, limit=None):
    """Approved guides with their average rating, in ONE query.

    Returns a list of (guide, average or None, number of reviews).
    OUTER JOIN keeps guides that have no reviews yet; GROUP BY gives one row
    per guide; AVG and COUNT are calculated by the database.
    """
    avg = func.avg(Review.rating)
    query = (
        db.select(GuideProfile, avg, func.count(Review.id))
        .outerjoin(Review, Review.guide_id == GuideProfile.id)
        .where(GuideProfile.status == "approved")
        .group_by(GuideProfile.id)
        .order_by(avg.desc().nulls_last(), GuideProfile.price_per_day_cents)
    )
    if country is not None:
        query = query.where(GuideProfile.country_id == country.id)
    if max_price_cents:
        query = query.where(GuideProfile.price_per_day_cents <= max_price_cents)
    if language:
        # icontains = case-insensitive LIKE '%arabic%'; autoescape treats % and _ typed by the user as normal letters
        query = query.where(GuideProfile.languages.icontains(language.strip(), autoescape=True))
    if limit:
        query = query.limit(limit)
    return [(guide, round(float(a), 1) if a is not None else None, n)
            for guide, a, n in db.session.execute(query).all()]


# ---------------------------------------------------------------------------
# Country search (homepage boarding-pass search and countries page)
# ---------------------------------------------------------------------------
def search_countries(month=None, max_budget_cents=None, days=7, interests=None, travelers=1,
                     no_visa_only=False):
    """Countries matching the filters, each with an estimated trip price.

    The estimate = cheapest upcoming flight (in that month if given)
                 + cheapest stay x nights + typical daily spending x days.
    A country with no flight in the chosen month is still shown (without a
    flight price) unless a budget is set, because then we can't promise it fits.
    no_visa_only keeps countries a Lebanese passport can enter with no visa
    arranged in advance (visa-free or visa on arrival).
    """
    interests = [i.lower() for i in (interests or [])]
    nights = max(days - 1, 1)
    results = []
    for country in all_countries():
        if interests and not set(interests) & set(country.tag_list()):
            continue
        if no_visa_only and not country.no_visa_in_advance:
            continue
        flight = cheapest_flight(country, month)
        stays = search_stays(country)
        estimate = estimate_trip_cost(country=country, flight=flight, stay=stays[0] if stays else None,
                                      nights=nights, days=days, travelers=travelers)
        if max_budget_cents and (flight is None or estimate["total_cents"] > max_budget_cents):
            continue
        results.append({
            "country": country,
            "flight": flight,
            "estimate": estimate,
            "warm": month in country.warm_month_list() if month else None,
        })
    # Warm countries first (when a month is chosen), then the most popular with Lebanese, then the cheapest
    results.sort(key=lambda r: (r["warm"] is False, -r["country"].popularity, r["estimate"]["total_cents"]))
    return results
