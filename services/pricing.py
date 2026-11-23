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
