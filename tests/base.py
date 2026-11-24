"""Shared set-up for every test file.

The idea:
1. Before the app is imported, DATABASE_URL is pointed at a TEMPORARY SQLite
   file, so the tests never touch your real database (instance/rihla.db).
2. The sample data (seed.py) is created ONCE in that file and a copy is kept.
3. Before EVERY test, the copy is put back. So each test starts from exactly
   the same sample data, whatever the previous test booked or deleted, and the
   tests can run in any order.

The sample data uses fixed dates (flights from December 2026 to 2027), so the
tests expect to run before those flights leave.
"""
import atexit
import os
import re
import shutil
import tempfile
import unittest

# ---- 1. Temporary database (must happen BEFORE "from app import app") ----
TEMP_DIR = tempfile.mkdtemp(prefix="rihla-tests-")
DB_FILE = os.path.join(TEMP_DIR, "test.db")
SEED_COPY = os.path.join(TEMP_DIR, "seed-copy.db")
os.environ["DATABASE_URL"] = "sqlite:///" + DB_FILE.replace("\\", "/")
# The AI agent always runs in demo mode during tests: no API key, no internet.
os.environ["AI_PROVIDER"] = "none"
os.environ["AI_API_KEY"] = ""
atexit.register(shutil.rmtree, TEMP_DIR, ignore_errors=True)

from app import app  # noqa: E402  (has to come after the lines above)
from extensions import db  # noqa: E402
from models import User  # noqa: E402

app.config["TESTING"] = True
DEFAULT_CHAT_LIMIT = app.config["CHAT_LIMIT_PER_HOUR"]
DEFAULT_MODEL = app.config["AI_MODEL"]


def _close_database():
    """Close every connection, so the database file can be replaced (Windows
    does not allow replacing a file that is still open)."""
    db.session.remove()
    db.engine.dispose()


def _create_seed_copy():
    """Build the sample data once and keep a copy of the file."""
    if os.path.exists(SEED_COPY):
        return
    from seed import seed_database
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_database()
        _close_database()
    shutil.copyfile(DB_FILE, SEED_COPY)


class RihlaTestCase(unittest.TestCase):
    """Base class: every test gets fresh sample data and a browser-like client."""

    def setUp(self):
        _create_seed_copy()                          # only does the work the first time
        shutil.copyfile(SEED_COPY, DB_FILE)          # back to the original sample data
        app.config["AI_PROVIDER"] = "none"
        app.config["AI_API_KEY"] = ""
        app.config["AI_MODEL"] = DEFAULT_MODEL
        app.config["CHAT_LIMIT_PER_HOUR"] = DEFAULT_CHAT_LIMIT
        self.ctx = app.app_context()
        self.ctx.push()
        self.client = app.test_client()              # acts like a browser (keeps cookies)

    def tearDown(self):
        _close_database()
        self.ctx.pop()

    # ---- helpers used by many tests ----
    def token(self, url="/"):
        """Open a page and read the CSRF token from its hidden form field."""
        html = self.client.get(url).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def login(self, email, password):
        return self.client.post("/login", data={"csrf_token": self.token("/login"),
                                                "email": email, "password": password})

    def logout(self):
        self.client.post("/logout", data={"csrf_token": self.token()})

    def page(self, url):
        """Text of a page (GET)."""
        return self.client.get(url).get_data(as_text=True)

    @staticmethod
    def user(email):
        return User.query.filter_by(email=email).first()
