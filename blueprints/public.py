"""Pages anyone can see (no login needed): homepage, countries, guides."""
from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from extensions import db
from models import Flight, GuideProfile, Review, Stay
from services import search
from services.pricing import dollars_to_cents, estimate_trip_cost, format_money

public_bp = Blueprint("public", __name__)

# A CSS "poster" (colours + emoji) for each country, used instead of photos
# so the site works offline during the demo. See static/css/style.css.
POSTER_ICONS = {"italy": "🏛️", "japan": "⛩️", "greece": "🏺", "turkey": "🕌", "egypt": "🐪", "thailand": "🛕"}


@public_bp.app_context_processor
def inject_globals():
    """Variables available in EVERY template."""
    return {"poster_icons": POSTER_ICONS, "month_names": search.MONTH_NAMES}


def int_arg(name, low, high, default=None):
    """Read a whole number from the URL (?name=5). Out of range or not a number -> default."""
    try:
        value = int(request.args.get(name, ""))
    except ValueError:
        return default
    return value if low <= value <= high else default


@public_bp.route("/")
def home():
    countries = search.all_countries()
    top_guides = search.guides_with_ratings(limit=4)
    return render_template("public/home.html", countries=countries, top_guides=top_guides,
                           interests=search.all_interests())


@public_bp.route("/countries")
def countries():
    # The homepage widget can pick one destination: go straight to its page.
    destination = request.args.get("to")
    if destination:
        country = search.get_country(destination)
        if country:
            return redirect(url_for("public.country", slug=country.slug))

    # Read and check the filters from the URL (they are just GET parameters).
    filters = {
        "month": int_arg("month", 1, 12),
        "days": int_arg("days", 1, 30, default=7),
        "travelers": int_arg("travelers", 1, 9, default=1),
        "budget": request.args.get("budget", "").strip(),
        "interest": request.args.get("interest", "").strip().lower(),
    }
    budget_cents = dollars_to_cents(filters["budget"]) if filters["budget"] else None
    interests = search.all_interests()
    if filters["interest"] not in interests:
        filters["interest"] = ""

    results = search.search_countries(
        month=filters["month"], max_budget_cents=budget_cents, days=filters["days"],
        interests=[filters["interest"]] if filters["interest"] else None, travelers=filters["travelers"],
    )
    return render_template("public/countries.html", results=results, filters=filters, interests=interests)


@public_bp.route("/countries/<slug>")
def country(slug):
    country = search.get_country(slug)
    if country is None:
        abort(404)
    return render_template(
        "public/country.html",
        country=country,
        flights=search.upcoming_flights(country),
        stays=search.search_stays(country),
        guides=search.guides_with_ratings(country),
        monuments=sorted(country.monuments, key=lambda m: m.entry_cost_cents),
        restaurants=sorted(country.restaurants, key=lambda r: r.avg_meal_cost_cents),
    )


@public_bp.route("/guides/<int:guide_id>")
def guide_profile(guide_id):
    guide = db.session.get(GuideProfile, guide_id)
    if guide is None or guide.status != "approved":  # pending/rejected guides are invisible
        abort(404)
    reviews = db.session.execute(
        db.select(Review).where(Review.guide_id == guide.id).order_by(Review.created_at.desc())
    ).scalars().all()
    return render_template("public/guide.html", guide=guide, reviews=reviews,
                           average=guide.average_rating(), count=len(reviews))


@public_bp.route("/api/estimate")
def api_estimate():
    """JSON for the trip calculator (called with fetch() from calculator.js).

    Example: /api/estimate?country=italy&flight_id=2&stay_id=3&nights=6
             &guide_id=1&guide_days=2&monument_ids=1,4&days=7&travelers=2
    Every id must belong to the chosen country, otherwise it is ignored.
    """
    country = search.get_country(request.args.get("country", ""))
    if country is None:
        return jsonify({"error": "Unknown country"}), 404

    def item(model, arg):
        obj = db.session.get(model, int_arg(arg, 1, 10**9) or 0)
        return obj if obj is not None and obj.country_id == country.id else None

    guide = item(GuideProfile, "guide_id")
    if guide is not None and guide.status != "approved":
        guide = None
    monument_ids = {int(x) for x in request.args.get("monument_ids", "").split(",") if x.strip().isdigit()}
    monuments = [m for m in country.monuments if m.id in monument_ids]

    estimate = estimate_trip_cost(
        country=country,
        flight=item(Flight, "flight_id"),
        stay=item(Stay, "stay_id"),
        nights=int_arg("nights", 0, 60, default=0),
        guide=guide,
        guide_days=int_arg("guide_days", 0, 30, default=0),
        monuments=monuments,
        days=int_arg("days", 0, 60, default=0),
        travelers=int_arg("travelers", 1, 9, default=1),
    )
    # Add ready-to-show text so the JavaScript does not need to format money.
    for line in estimate["lines"]:
        line["total"] = format_money(line["total_cents"])
    estimate["total"] = format_money(estimate["total_cents"])
    return jsonify(estimate)
