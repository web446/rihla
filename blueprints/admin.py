"""Admin-only pages. Every route has @role_required("admin").

  /admin/                      dashboard: revenue, commission, bookings, pending guides
  /admin/guides                approve / reject guides
  /admin/content/<resource>    list + add / edit / delete countries, monuments,
                               restaurants, stays, flights (see admin_resources.py)
  /admin/bookings              every booking on the platform
  /admin/settings              the commission percentage
"""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from blueprints.admin_resources import RESOURCES, delete_problem, form_values, read_form
from extensions import db
from models import Booking, BookingItem, Country, GuideProfile, Setting, User
from security import role_required
from services import search
from services.pricing import get_commission_rate

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_bp.route("/")
@role_required("admin")
def dashboard():
    confirmed = Booking.status == "confirmed"

    # One query: count + 3 sums over all confirmed bookings
    count, revenue, commission, providers = db.session.execute(
        db.select(func.count(Booking.id), func.coalesce(func.sum(Booking.total_cents), 0),
                  func.coalesce(func.sum(Booking.commission_cents), 0),
                  func.coalesce(func.sum(Booking.provider_cents), 0)).where(confirmed)
    ).one()

    # Commission split by what was sold (flights / stays / guides): GROUP BY
    by_type = dict(db.session.execute(
        db.select(BookingItem.item_type, func.sum(BookingItem.commission_cents))
        .join(Booking).where(confirmed).group_by(BookingItem.item_type)
    ).all())


    # Revenue per country (every item of a trip is in the same country)
    per_country = {}
    for booking in db.session.execute(db.select(Booking).where(confirmed)).scalars():
        name = booking.country.name if booking.country else "?"
        per_country[name] = per_country.get(name, 0) + booking.total_cents
    per_country = sorted(per_country.items(), key=lambda kv: kv[1], reverse=True)

    users = dict(db.session.execute(db.select(User.role, func.count(User.id)).group_by(User.role)).all())
    pending_guides = db.session.execute(
        db.select(func.count(GuideProfile.id)).where(GuideProfile.status == "pending")).scalar()
    recent = db.session.execute(db.select(Booking).order_by(Booking.created_at.desc()).limit(6)).scalars().all()
    cancelled = db.session.execute(db.select(func.count(Booking.id)).where(Booking.status == "cancelled")).scalar()

    return render_template(
        "admin/dashboard.html",
        stats={"count": count, "revenue": revenue, "commission": commission, "providers": providers,
               "cancelled": cancelled, "pending_guides": pending_guides, "users": users,
               "rate": get_commission_rate()},
        by_type=by_type, per_country=per_country, recent=recent,
        resources=RESOURCES,
    )


# ---------------------------------------------------------------------------
# Guide approval
# ---------------------------------------------------------------------------
@admin_bp.route("/guides")
@role_required("admin")
def guides():
    status = request.args.get("status", "pending")
    if status not in ("pending", "approved", "rejected"):
        status = "pending"
    profiles = db.session.execute(
        db.select(GuideProfile).where(GuideProfile.status == status).order_by(GuideProfile.id.desc())
    ).scalars().all()
    counts = dict(db.session.execute(
        db.select(GuideProfile.status, func.count()).group_by(GuideProfile.status)).all())
    ratings = {g.id: (avg, n) for g, avg, n in search.guides_with_ratings()}
    return render_template("admin/guides.html", profiles=profiles, status=status, counts=counts, ratings=ratings)


@admin_bp.route("/guides/<int:guide_id>/status", methods=["POST"])
@role_required("admin")
def set_guide_status(guide_id):
    """Approve or reject a guide (POST + CSRF token, like every change)."""
    profile = db.session.get(GuideProfile, guide_id)
    new_status = request.form.get("status")
    if profile is None or new_status not in ("approved", "rejected", "pending"):
        flash("Invalid request.", "danger")
        return redirect(url_for("admin.guides"))
    profile.status = new_status
    db.session.commit()
    verb = {"approved": "approved ✅ and now visible to travelers", "rejected": "rejected",
            "pending": "moved back to pending"}[new_status]
    flash(f"{profile.user.full_name} was {verb}.", "success" if new_status == "approved" else "info")
    return redirect(url_for("admin.guides", status=request.form.get("back", "pending")))


# ---------------------------------------------------------------------------
# Content CRUD (one set of routes for all 5 tables)
# ---------------------------------------------------------------------------
def _resource_or_404(key):
    resource = RESOURCES.get(key)
    if resource is None:
        abort(404)
    return resource


def _countries():
    return db.session.execute(db.select(Country).order_by(Country.name)).scalars().all()


@admin_bp.route("/content/<key>")
@role_required("admin")
def content_list(key):
    resource = _resource_or_404(key)
    query = db.select(resource.model).order_by(resource.order_by)
    country = search.get_country(request.args.get("country", "")) if resource.has_country else None
    if country:
        query = query.where(resource.model.country_id == country.id)
    rows = db.session.execute(query).scalars().all()
    return render_template("admin/list.html", resource=resource, rows=rows, resources=RESOURCES,
                           countries=_countries(), country=country)


@admin_bp.route("/content/<key>/new", methods=["GET", "POST"])
@admin_bp.route("/content/<key>/<int:item_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def content_form(key, item_id=None):
    """CREATE (no item_id) and UPDATE (with item_id) share one form."""
    resource = _resource_or_404(key)
    obj = None
    if item_id is not None:
        obj = db.session.get(resource.model, item_id)
        if obj is None:
            abort(404)
    countries = _countries()

    if request.method == "GET":
        values = form_values(resource, obj) if obj else {"country_id": request.args.get("country_id", "")}
        return render_template("admin/form.html", resource=resource, obj=obj, values=values, errors={},
                               countries=countries, resources=RESOURCES)

    errors, cleaned, raw = read_form(resource, request.form, {c.id for c in countries})
    if not errors and resource.extra_check:
        errors = resource.extra_check(cleaned, obj)
    if errors:
        return render_template("admin/form.html", resource=resource, obj=obj, values=raw, errors=errors,
                               countries=countries, resources=RESOURCES), 400

    if obj is None:
        obj = resource.model()
        db.session.add(obj)
        if key == "flights":
            obj.seats_available = cleaned["seats_total"]       # a new plane is empty
    elif key == "flights":
        # keep the number of seats already sold: available changes by the same amount as total
        obj.seats_available += cleaned["seats_total"] - obj.seats_total
    for name, value in cleaned.items():
        setattr(obj, name, value)
    db.session.commit()
    flash(f"{resource.singular.capitalize()} saved.", "success")
    return redirect(url_for("admin.content_list", key=key))


@admin_bp.route("/content/<key>/<int:item_id>/delete", methods=["POST"])
@role_required("admin")
def content_delete(key, item_id):
    resource = _resource_or_404(key)
    obj = db.session.get(resource.model, item_id)
    if obj is None:
        abort(404)
    problem = delete_problem(resource, obj)
    if problem:
        flash(problem, "warning")
    else:
        db.session.delete(obj)
        db.session.commit()
        flash(f"{resource.singular.capitalize()} deleted.", "info")
    return redirect(url_for("admin.content_list", key=key))


# ---------------------------------------------------------------------------
# All bookings + settings
# ---------------------------------------------------------------------------
@admin_bp.route("/bookings")
@role_required("admin")
def bookings():
    status = request.args.get("status", "")
    query = db.select(Booking).order_by(Booking.created_at.desc())
    if status in ("confirmed", "cancelled"):
        query = query.where(Booking.status == status)
    rows = db.session.execute(query).scalars().all()
    totals = {
        "total": sum(b.total_cents for b in rows if b.status == "confirmed"),
        "commission": sum(b.commission_cents for b in rows if b.status == "confirmed"),
        "provider": sum(b.provider_cents for b in rows if b.status == "confirmed"),
    }
    return render_template("admin/bookings.html", rows=rows, totals=totals, status=status,
                           today=date.today())


@admin_bp.route("/settings", methods=["GET", "POST"])
@role_required("admin")
def settings():
    error = None
    if request.method == "POST":
        text = (request.form.get("commission_rate") or "").strip()
        try:
            rate = round(float(text), 2)
        except ValueError:
            rate = None
        if rate is None or not 0 <= rate <= 50:
            error = "Enter a percentage between 0 and 50."
        else:
            Setting.set("commission_rate", f"{rate:g}")
            db.session.commit()
            flash(f"Commission set to {rate:g}%. It applies to NEW bookings only.", "success")
            return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", rate=get_commission_rate(), error=error), (400 if error else 200)
