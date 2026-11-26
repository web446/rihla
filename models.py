"""Database tables, written as Python classes (Flask-SQLAlchemy models).

One class = one table, one attribute = one column, one object = one row.
db.create_all() (run by "flask --app app init-db") turns these classes into
real tables.

MONEY RULE: every price is stored as a whole number of CENTS (an Integer).
$12.50 is stored as 1250. Integers are exact, while decimal numbers stored as
floats can give rounding errors like 0.1 + 0.2 = 0.30000000000000004.
That matters when we split every booking into commission + provider share.
Columns that hold money end in "_cents" so this is never confusing.
"""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

# Allowed values for "choice" columns. They are checked in Python (validators)
# AND, for the important ones, by a CheckConstraint inside the database.
ROLES = ("traveler", "guide", "admin")
GUIDE_STATUSES = ("pending", "approved", "rejected")
STAY_TYPES = ("hotel", "apartment")
PRICE_RANGES = ("$", "$$", "$$$")
ITEM_TYPES = ("flight", "stay", "guide")
# How a Lebanese passport holder enters a country
ENTRY_TYPES = ("visa_free", "visa_on_arrival", "conditional", "evisa")
ENTRY_LABELS = {
    "visa_free": "Visa-free",
    "visa_on_arrival": "Visa on arrival",
    "conditional": "Visa-free (conditions)",
    "evisa": "e-Visa online",
}


def now():
    return datetime.now()


# --------------------------------------------------------------------------
# Users and guides
# --------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="ck_user_role"),)

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    # Only the HASH is stored, never the password itself.
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="traveler")
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    # uselist=False: a user has at most ONE guide profile (one-to-one)
    guide_profile = db.relationship("GuideProfile", back_populates="user", uselist=False)
    bookings = db.relationship("Booking", back_populates="traveler")

    def set_password(self, password):
        # generate_password_hash adds a random "salt" and hashes many times,
        # so two users with the same password still get different hashes.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Hashes the typed password the same way and compares the results.
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class GuideProfile(db.Model):
    __tablename__ = "guide_profiles"
    __table_args__ = (
        CheckConstraint(f"status IN {GUIDE_STATUSES}", name="ck_guide_status"),
        CheckConstraint("price_per_day_cents > 0", name="ck_guide_price"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)
    languages = db.Column(db.String(150), nullable=False)  # "English, Arabic, Italian"
    bio = db.Column(db.Text, nullable=False)
    price_per_day_cents = db.Column(db.Integer, nullable=False)
    # New guides wait for an admin: only "approved" guides are shown publicly.
    status = db.Column(db.String(10), nullable=False, default="pending")
    photo = db.Column(db.String(255))

    user = db.relationship("User", back_populates="guide_profile")
    country = db.relationship("Country", back_populates="guides")
    reviews = db.relationship("Review", back_populates="guide")

    def average_rating(self):
        """Star rating = AVG of this guide's reviews, calculated by the database.

        It is NOT stored in a column, so it can never be out of date.
        Returns None when the guide has no reviews yet.
        """
        avg = db.session.query(func.avg(Review.rating)).filter(Review.guide_id == self.id).scalar()
        return round(float(avg), 1) if avg is not None else None

    def review_count(self):
        return db.session.query(func.count(Review.id)).filter(Review.guide_id == self.id).scalar()

    def language_list(self):
        return [lang.strip() for lang in self.languages.split(",") if lang.strip()]


# --------------------------------------------------------------------------
# Destinations: a country and everything inside it
# --------------------------------------------------------------------------
class Country(db.Model):
    __tablename__ = "countries"
    __table_args__ = (
        CheckConstraint(f"entry_type IN {ENTRY_TYPES}", name="ck_country_entry"),
        CheckConstraint("popularity BETWEEN 1 AND 5", name="ck_country_popularity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)  # used in URLs: /countries/italy
    tagline = db.Column(db.String(150))
    description = db.Column(db.Text, nullable=False)
    best_time = db.Column(db.String(100), nullable=False)
    currency = db.Column(db.String(50), nullable=False)
    language = db.Column(db.String(50), nullable=False)
    # Months (1-12) with warm weather, e.g. "3,4,5". Used by "somewhere warm in March".
    warm_months = db.Column(db.String(40), nullable=False, default="")
    tags = db.Column(db.String(150), nullable=False, default="")  # "beach,history,food"
    # Typical spending per person per day on food + local transport.
    avg_daily_spend_cents = db.Column(db.Integer, nullable=False, default=0)
    # Real photo (Wikimedia Commons). Free licences require crediting the author,
    # so the credit ("Author · CC BY-SA 4.0") and the file's page are stored with it.
    hero_image = db.Column(db.String(500))
    hero_credit = db.Column(db.String(300))
    hero_source = db.Column(db.String(500))

    # --- Entry rules for an ordinary LEBANESE passport (Rihla's travelers fly from Beirut) ---
    entry_type = db.Column(db.String(20), nullable=False, default="visa_free")   # see ENTRY_TYPES
    max_stay = db.Column(db.String(60), nullable=False, default="")             # "90 days in any 180"
    entry_notes = db.Column(db.Text, nullable=False, default="")                # conditions to know
    # How popular the country is with Lebanese travelers, 1-5 stars, and why
    popularity = db.Column(db.Integer, nullable=False, default=3)
    popularity_note = db.Column(db.String(200), nullable=False, default="")

    # cascade="all, delete-orphan": deleting a country also deletes its children.
    monuments = db.relationship("Monument", back_populates="country", cascade="all, delete-orphan")
    restaurants = db.relationship("Restaurant", back_populates="country", cascade="all, delete-orphan")
    stays = db.relationship("Stay", back_populates="country", cascade="all, delete-orphan")
    flights = db.relationship("Flight", back_populates="country", cascade="all, delete-orphan")
    guides = db.relationship("GuideProfile", back_populates="country")

    @property
    def entry_label(self):
        return ENTRY_LABELS.get(self.entry_type, self.entry_type)

    @property
    def no_visa_in_advance(self):
        """True when a Lebanese traveler can just fly in (visa-free or visa on arrival)."""
        return self.entry_type in ("visa_free", "visa_on_arrival")

    def has_direct_flight(self):
        """At least one upcoming non-stop flight from Beirut."""
        today = date.today()
        return any(f.stops.startswith("Direct") and f.depart_date > today for f in self.flights)

    def warm_month_list(self):
        return [int(m) for m in self.warm_months.split(",") if m.strip()]

    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class Monument(db.Model):
    __tablename__ = "monuments"
    __table_args__ = (CheckConstraint("entry_cost_cents >= 0", name="ck_monument_cost"),)

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    entry_cost_cents = db.Column(db.Integer, nullable=False, default=0)  # 0 = free
    image = db.Column(db.String(500))          # real photo URL (Wikimedia Commons)
    image_credit = db.Column(db.String(300))   # "Author · licence", shown under the photo
    image_source = db.Column(db.String(500))   # the photo's page on Wikimedia Commons

    country = db.relationship("Country", back_populates="monuments")


class Restaurant(db.Model):
    __tablename__ = "restaurants"
    __table_args__ = (CheckConstraint(f"price_range IN {PRICE_RANGES}", name="ck_restaurant_price"),)

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    must_try_dish = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price_range = db.Column(db.String(3), nullable=False)
    avg_meal_cost_cents = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(255))

    country = db.relationship("Country", back_populates="restaurants")


class Stay(db.Model):
    """A hotel or an Airbnb-style apartment."""
    __tablename__ = "stays"
    __table_args__ = (
        CheckConstraint(f"type IN {STAY_TYPES}", name="ck_stay_type"),
        CheckConstraint("price_per_night_cents > 0", name="ck_stay_price"),
    )

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price_per_night_cents = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float, nullable=False, default=0)  # out of 5, display only
    image = db.Column(db.String(255))

    country = db.relationship("Country", back_populates="stays")


class Flight(db.Model):
    """A round-trip flight from Beirut. price_cents is per seat."""
    __tablename__ = "flights"
    __table_args__ = (
        # The database itself refuses negative seats or more seats than the plane has.
        CheckConstraint("seats_available >= 0 AND seats_available <= seats_total", name="ck_flight_seats"),
        CheckConstraint("return_date >= depart_date", name="ck_flight_dates"),
    )

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)
    airline = db.Column(db.String(60), nullable=False)
    flight_number = db.Column(db.String(12), nullable=False)
    from_city = db.Column(db.String(60), nullable=False, default="Beirut")
    to_city = db.Column(db.String(60), nullable=False)
    stops = db.Column(db.String(60), nullable=False, default="Direct")  # "Direct" or "via Doha"
    depart_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    seats_total = db.Column(db.Integer, nullable=False)
    seats_available = db.Column(db.Integer, nullable=False)

    country = db.relationship("Country", back_populates="flights")


# --------------------------------------------------------------------------
# Bookings
# --------------------------------------------------------------------------
class Booking(db.Model):
    """One trip. Its flight / stay / guide are rows in booking_items."""
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_booking_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    traveler_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_cents = db.Column(db.Integer, nullable=False)        # what the traveler pays
    # A COPY of the commission % at booking time: if the admin changes the rate
    # later, old bookings keep the rate they were really charged.
    commission_rate = db.Column(db.Float, nullable=False)
    commission_cents = db.Column(db.Integer, nullable=False)   # platform earnings
    provider_cents = db.Column(db.Integer, nullable=False)     # owed to airline/hotel/guide
    status = db.Column(db.String(10), nullable=False, default="confirmed")
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    traveler = db.relationship("User", back_populates="bookings")
    items = db.relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")

    @property
    def country(self):
        """The trip's country (every item of a trip is in the same country)."""
        return self.items[0].target.country if self.items else None

    @property
    def nights(self):
        return (self.end_date - self.start_date).days


class BookingItem(db.Model):
    """One line of a booking. Exactly ONE of flight_id / stay_id / guide_id is set.

    Three real foreign keys (instead of one generic "item_id") let the database
    check that the flight, stay or guide really exists.
    """
    __tablename__ = "booking_items"
    __table_args__ = (
        CheckConstraint(f"item_type IN {ITEM_TYPES}", name="ck_item_type"),
        CheckConstraint("quantity > 0", name="ck_item_quantity"),
        CheckConstraint(
            "(CASE WHEN flight_id IS NOT NULL THEN 1 ELSE 0 END)"
            " + (CASE WHEN stay_id IS NOT NULL THEN 1 ELSE 0 END)"
            " + (CASE WHEN guide_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_item_one_target",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    item_type = db.Column(db.String(10), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey("flights.id"))
    stay_id = db.Column(db.Integer, db.ForeignKey("stays.id"))
    guide_id = db.Column(db.Integer, db.ForeignKey("guide_profiles.id"))
    quantity = db.Column(db.Integer, nullable=False)  # seats, nights or days
    unit_price_cents = db.Column(db.Integer, nullable=False)
    line_total_cents = db.Column(db.Integer, nullable=False)
    commission_cents = db.Column(db.Integer, nullable=False)
    provider_cents = db.Column(db.Integer, nullable=False)

    booking = db.relationship("Booking", back_populates="items")
    flight = db.relationship("Flight")
    stay = db.relationship("Stay")
    guide = db.relationship("GuideProfile")
    review = db.relationship("Review", back_populates="booking_item", uselist=False)

    @property
    def target(self):
        """The booked flight, stay or guide, whichever this line is."""
        return self.flight or self.stay or self.guide

    @property
    def title(self):
        if self.item_type == "flight":
            return f"{self.flight.airline} {self.flight.flight_number} · Beirut → {self.flight.to_city}"
        if self.item_type == "stay":
            return f"{self.stay.name}, {self.stay.city}"
        return f"Guide: {self.guide.user.full_name}"

    @property
    def unit(self):
        return {"flight": "seat(s)", "stay": "night(s)", "guide": "day(s)"}[self.item_type]


class Review(db.Model):
    """A traveler's rating of a guide they actually booked.

    booking_item_id is UNIQUE, so the database allows only one review per
    booked guide.
    """
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),)

    id = db.Column(db.Integer, primary_key=True)
    booking_item_id = db.Column(db.Integer, db.ForeignKey("booking_items.id"), unique=True, nullable=False)
    guide_id = db.Column(db.Integer, db.ForeignKey("guide_profiles.id"), nullable=False)
    traveler_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    booking_item = db.relationship("BookingItem", back_populates="review")
    guide = db.relationship("GuideProfile", back_populates="reviews")
    traveler = db.relationship("User")


class Setting(db.Model):
    """Key/value settings the admin can change, e.g. commission_rate = "10"."""
    __tablename__ = "settings"

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=False)

    @staticmethod
    def get(key, default=None):
        row = db.session.get(Setting, key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = db.session.get(Setting, key)
        if row:
            row.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))
