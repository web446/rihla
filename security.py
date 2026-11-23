"""Login sessions, role protection and CSRF protection.

How login works in Flask:
  * `session` is a dictionary saved in a cookie that Flask SIGNS with
    SECRET_KEY. The browser can read it but cannot change it without
    breaking the signature, so `session["user_id"]` can be trusted.
  * After login we store only the user's id. On every request we load the
    user from the database again (load_current_user), so a deleted user or
    a changed role takes effect immediately.
"""
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import abort, flash, g, redirect, request, session, url_for

from extensions import db
from models import User

# Where each role lands after logging in
HOME_FOR_ROLE = {
    "traveler": "traveler.trips",
    "guide": "guide.dashboard",
    "admin": "admin.dashboard",
}


# ---------------------------------------------------------------------------
# Logging in and out
# ---------------------------------------------------------------------------
def login_user(user):
    # clear() first: throw away anything from before login (protects against
    # "session fixation", where an attacker prepares a session in advance).
    session.clear()
    session["user_id"] = user.id
    session.permanent = True  # keep the login after the browser closes (31 days by default)


def logout_user():
    session.clear()


def load_current_user():
    """Runs before EVERY request (registered in app.py).

    g is Flask's per-request storage: g.user is the logged-in User or None.
    """
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None
    if user_id and g.user is None:
        session.clear()  # the account was deleted


def home_url_for(user):
    return url_for(HOME_FOR_ROLE.get(user.role, "public.home"))


def is_safe_next_url(target):
    """Only allow redirects to pages of THIS site after login.

    Without this, a link like /login?next=https://evil.com would send the
    user to another website right after they log in ("open redirect").
    """
    if not target:
        return False
    parts = urlparse(target)
    return parts.scheme == "" and parts.netloc == "" and target.startswith("/") and not target.startswith("//")


# ---------------------------------------------------------------------------
# Protecting pages
# ---------------------------------------------------------------------------
def role_required(*roles):
    """Decorator: only logged-in users with one of `roles` may open the page.

        @bp.route("/admin/")
        @role_required("admin")
        def dashboard(): ...

      * not logged in  -> redirect to the login page (then back here)
      * wrong role     -> 403 Forbidden
    """
    def decorator(view):
        @wraps(view)  # keeps the original function name, which Flask needs
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
            if g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------
# CSRF = another website secretly submitting a form to OUR site while the
# user is logged in (e.g. a hidden "cancel booking" form). Defence: every
# form we render contains a secret random token that is also stored in the
# session. Another website cannot read that token, so it cannot send it.
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def check_csrf():
    """Runs before every request: refuse POST/PUT/DELETE without a valid token.

    Forms send it as a hidden field "csrf_token"; JavaScript fetch() calls
    send it in an "X-CSRF-Token" header.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    expected = session.get("csrf_token")
    # compare_digest compares in constant time (does not leak timing information)
    if not sent or not expected or not secrets.compare_digest(sent, expected):
        abort(400, description="Your form expired or is invalid. Please reload the page and try again.")
