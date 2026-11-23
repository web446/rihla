"""Sign up, log in, log out."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Country, GuideProfile, User
from security import home_url_for, is_safe_next_url, login_user, logout_user
from validators import validate_guide_registration, validate_login, validate_registration

auth_bp = Blueprint("auth", __name__)


def _email_taken(email):
    return db.session.execute(db.select(User.id).filter_by(email=email)).first() is not None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:  # already logged in
        return redirect(home_url_for(g.user))

    next_url = request.values.get("next", "")
    if request.method == "GET":
        return render_template("auth/login.html", errors={}, values={}, next_url=next_url)

    errors, cleaned = validate_login(request.form)
    user = None
    if not errors:
        user = db.session.execute(db.select(User).filter_by(email=cleaned["email"])).scalar_one_or_none()
        # ONE message for "no such email" and "wrong password": an attacker
        # must not be able to find out which emails have an account.
        if user is None or not user.check_password(cleaned["password"]):
            errors["form"] = "Wrong email or password."

    if errors:
        return render_template("auth/login.html", errors=errors,
                               values={"email": cleaned["email"]}, next_url=next_url), 400

    login_user(user)
    flash(f"Welcome back, {user.full_name.split()[0]}!", "success")
    if is_safe_next_url(next_url):
        return redirect(next_url)
    return redirect(home_url_for(user))


@auth_bp.route("/logout", methods=["POST"])  # POST (with CSRF token), so a link on another site can't log you out
def logout():
    logout_user()
    flash("You are logged out. See you on your next trip!", "info")
    return redirect(url_for("public.home"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Traveler sign-up."""
    if g.user:
        return redirect(home_url_for(g.user))
    if request.method == "GET":
        return render_template("auth/register.html", errors={}, values={})

    errors, cleaned = validate_registration(request.form)
    if not errors and _email_taken(cleaned["email"]):
        errors["email"] = "An account with this email already exists."
    if errors:
        cleaned.pop("password", None)  # never send the password back to the page
        return render_template("auth/register.html", errors=errors, values=cleaned), 400

    user = User(full_name=cleaned["full_name"], email=cleaned["email"], role="traveler")
    user.set_password(cleaned["password"])  # hashed inside set_password()
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:  # two sign-ups with the same email at the same moment
        db.session.rollback()
        return render_template("auth/register.html", values=cleaned,
                               errors={"email": "An account with this email already exists."}), 400

    login_user(user)
    flash("Your account is ready. Where to first?", "success")
    return redirect(url_for("public.home"))


@auth_bp.route("/register/guide", methods=["GET", "POST"])
def register_guide():
    """Guide sign-up: creates a User (role guide) + a GuideProfile with status 'pending'."""
    if g.user:
        return redirect(home_url_for(g.user))
    countries = db.session.execute(db.select(Country).order_by(Country.name)).scalars().all()
    if request.method == "GET":
        return render_template("auth/register_guide.html", errors={}, values={}, countries=countries)

    errors, cleaned = validate_guide_registration(request.form, {c.id for c in countries})
    if not errors and _email_taken(cleaned["email"]):
        errors["email"] = "An account with this email already exists."
    if errors:
        cleaned.pop("password", None)
        return render_template("auth/register_guide.html", errors=errors, values=cleaned,
                               countries=countries), 400

    user = User(full_name=cleaned["full_name"], email=cleaned["email"], role="guide")
    user.set_password(cleaned["password"])
    profile = GuideProfile(user=user, country_id=cleaned["country_id"], languages=cleaned["languages"],
                           bio=cleaned["bio"], price_per_day_cents=cleaned["price_per_day_cents"],
                           status="pending")  # invisible to travelers until an admin approves it
    db.session.add_all([user, profile])
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return render_template("auth/register_guide.html", values=cleaned, countries=countries,
                               errors={"email": "An account with this email already exists."}), 400

    login_user(user)
    flash("Thanks! Your guide profile was sent to our team for approval.", "success")
    return redirect(url_for("guide.dashboard"))
