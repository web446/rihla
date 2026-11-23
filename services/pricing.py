"""Money helpers: commission split and formatting.

All amounts are integers in cents (see the MONEY RULE in models.py).
"""
from decimal import ROUND_HALF_UP, Decimal

from models import Setting

DEFAULT_COMMISSION_RATE = 10  # percent


def get_commission_rate():
    """The current platform commission in percent (admin can change it)."""
    return float(Setting.get("commission_rate", DEFAULT_COMMISSION_RATE))


def split_commission(line_total_cents, rate_percent):
    """Split a price into (platform commission, provider share), in cents.

    Example with 10%:  $250.00 -> 25000 cents
        commission = 25000 * 10 / 100 = 2500   ($25.00 for the platform)
        provider   = 25000 - 2500     = 22500  ($225.00 for the guide/hotel)

    Decimal + ROUND_HALF_UP gives normal school rounding (x.5 rounds up),
    and provider = total - commission guarantees the two parts always add
    up to exactly the total, with no lost cent.
    """
    commission = Decimal(line_total_cents) * Decimal(str(rate_percent)) / 100
    commission_cents = int(commission.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return commission_cents, line_total_cents - commission_cents


def estimate_trip_cost(country=None, flight=None, stay=None, nights=0, guide=None, guide_days=0,
                       monuments=(), days=0, travelers=1):
    """Estimated total price of a trip, line by line (all in cents).

    Used by the calculator on the country page (through /api/estimate),
    the country search, and later the AI agent's estimate_trip_cost tool,
    so every part of the site gives the SAME number.

        flight       price per seat      x travelers
        stay         price per night     x nights        (one room for the group)
        guide        price per day       x guide days    (one guide for the group)
        activities   entry tickets       x travelers
        daily costs  food + transport    x days x travelers
    """
    travelers = max(int(travelers or 1), 1)
    lines = []

    def add(key, label, unit_cents, quantity, detail):
        if unit_cents is not None and quantity > 0:
            lines.append({"key": key, "label": label, "detail": detail,
                          "unit_cents": unit_cents, "quantity": quantity,
                          "total_cents": unit_cents * quantity})

    if flight:
        add("flight", f"Flight {flight.airline} {flight.flight_number}", flight.price_cents, travelers,
            f"{travelers} seat(s) x {format_money(flight.price_cents)}")
    if stay:
        add("stay", stay.name, stay.price_per_night_cents, nights,
            f"{nights} night(s) x {format_money(stay.price_per_night_cents)}")
    if guide:
        add("guide", f"Guide: {guide.user.full_name}", guide.price_per_day_cents, guide_days,
            f"{guide_days} day(s) x {format_money(guide.price_per_day_cents)}")
    tickets = sum(m.entry_cost_cents for m in monuments)
    if monuments:
        add("activities", f"{len(monuments)} monument ticket(s)", tickets, travelers,
            f"{travelers} traveler(s) x {format_money(tickets)}")
    if country and days > 0:
        add("daily", "Food & local transport", country.avg_daily_spend_cents, days * travelers,
            f"{days} day(s) x {travelers} traveler(s) x {format_money(country.avg_daily_spend_cents)}")

    return {"lines": lines, "total_cents": sum(line["total_cents"] for line in lines)}


def format_money(cents):
    """12345 -> "$123.45" (used as the |money filter in templates)."""
    if cents is None:
        return "-"
    return f"${cents / 100:,.2f}"


def dollars_to_cents(text):
    """Turn a typed amount like "120" or "99.90" into cents, or None if invalid."""
    try:
        value = Decimal(str(text).strip().replace(",", ""))
    except Exception:
        return None
    if not value.is_finite() or value < 0:  # rejects "NaN", "Infinity", "-5"
        return None
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
