"""Server-side form validation (same idea as the Chapter 9 lab).

Each validate_*() function takes request.form and returns a tuple:
    errors  : {field name: message}  (empty dict = everything is valid)
    cleaned : the trimmed / converted values, ready to save

The browser also checks the forms (required, minlength, type="email"...),
but those checks can be skipped, so the SERVER always checks again.
"""
import re

from services.pricing import dollars_to_cents

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


def _text(form, name):
    return (form.get(name) or "").strip()


def _check_name(errors, value):
    if len(value) < 2 or len(value) > 100:
        errors["full_name"] = "Please enter your name (2-100 characters)."


def _check_email(errors, value):
    if not EMAIL_RE.match(value) or len(value) > 150:
        errors["email"] = "Please enter a valid email address."


def _check_new_password(errors, password, confirm):
    if len(password) < 8:
        errors["password"] = "Use at least 8 characters."
    elif not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errors["password"] = "Use at least one letter and one number."
    if password != confirm:
        errors["confirm_password"] = "The two passwords do not match."


def validate_login(form):
    errors = {}
    cleaned = {"email": _text(form, "email").lower()}
    password = form.get("password") or ""
    if not cleaned["email"]:
        errors["email"] = "Enter your email."
    if not password:
        errors["password"] = "Enter your password."
    cleaned["password"] = password  # never trimmed: spaces can be part of a password
    return errors, cleaned


def validate_registration(form):
    """Traveler sign-up."""
    errors = {}
    cleaned = {
        "full_name": _text(form, "full_name"),
        "email": _text(form, "email").lower(),
    }
    _check_name(errors, cleaned["full_name"])
    _check_email(errors, cleaned["email"])
    password = form.get("password") or ""
    _check_new_password(errors, password, form.get("confirm_password") or "")
    cleaned["password"] = password
    return errors, cleaned


def validate_guide_profile(form, country_ids):
    """The guide part of a form: country, languages, bio, daily price.

    country_ids: the ids that exist in the database (so a fake id is refused).
    Used by guide sign-up AND by the guide's "edit profile" page.
    """
    errors = {}
    cleaned = {
        "languages": _text(form, "languages"),
        "bio": _text(form, "bio"),
        "price": _text(form, "price_per_day"),
    }

    try:
        cleaned["country_id"] = int(form.get("country_id", ""))
    except ValueError:
        cleaned["country_id"] = None
    if cleaned["country_id"] not in country_ids:
        errors["country_id"] = "Choose the country where you guide."

    languages = [lang.strip() for lang in cleaned["languages"].split(",") if lang.strip()]
    if not languages or len(cleaned["languages"]) > 150:
        errors["languages"] = "List at least one language, separated by commas."
    cleaned["languages"] = ", ".join(languages)

    if len(cleaned["bio"]) < 30 or len(cleaned["bio"]) > 1000:
        errors["bio"] = "Write a short bio (30-1000 characters)."

    cents = dollars_to_cents(cleaned["price"])
    if cents is None or cents < 1000 or cents > 100000:
        errors["price_per_day"] = "Enter a daily price between $10 and $1,000."
    cleaned["price_per_day_cents"] = cents
    return errors, cleaned


def validate_guide_registration(form, country_ids):
    """Guide sign-up = account fields + guide profile fields."""
    errors, cleaned = validate_registration(form)
    profile_errors, profile = validate_guide_profile(form, country_ids)
    errors.update(profile_errors)
    cleaned.update(profile)
    return errors, cleaned
