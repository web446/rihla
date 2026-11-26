# Rihla code guide

What every file does, how a request travels through the code, and answers to the questions we expect at the
presentation. Every answer gives the **file and function to open**. Line numbers are for the current version;
if a line moves, search for the function name.

---

## 1. The big picture

Rihla is split into the three classic parts of a web application, each in its own files:

| Part | Language | Where | Job |
|---|---|---|---|
| **Front end** | HTML (Jinja templates), CSS, JavaScript, Bootstrap 5 | `templates/`, `static/` | What the user sees and clicks |
| **Back end** | Python 3.12 + Flask 3 | `app.py`, `blueprints/`, `services/`, `security.py`, `validators.py`, `config.py` | Receives each request, checks it, applies the rules, answers with a page |
| **Database** | SQLite through Flask-SQLAlchemy | `models.py`, `extensions.py`, `seed.py`, `database/schema.sql`, `instance/rihla.db` | Stores users, countries, flights, bookings... |

### What happens when someone opens a page

```
Browser ──HTTP request──► app.py (Flask)
                            │ 1. security.load_current_user  → who is logged in? (g.user)
                            │ 2. security.check_csrf         → is this form genuine?
                            ▼
                       blueprints/*.py   (the route: one Python function per URL)
                            │ calls
                            ▼
                       services/*.py     (the business rules: booking, prices, search)
                            │ reads / writes
                            ▼
                       models.py ──► SQLite database (instance/rihla.db)
                            │
                            ▼
                       templates/*.html  (Jinja fills the HTML with the data)
Browser ◄──HTML page────────┘   + static/css/style.css, static/js/*.js
```

The routes never contain business rules, and the templates never contain SQL. Each layer has one job.

---

## 2. Every file and its purpose

### Back end (Python)

| File | Part | What it does |
|---|---|---|
| [app.py](../app.py) | Back end | **Starts the application.** `create_app()` builds the Flask app, connects the database, registers the 5 blueprints, the error pages (403, 404, 400) and the terminal commands `init-db` (reset the database with sample data) and `db-summary`. The last line `app = create_app()` is what `flask run` and `gunicorn app:app` use. |
| [config.py](../config.py) | Back end | **Settings.** Reads `SECRET_KEY` and `DATABASE_URL` from the environment (or the `.env` file). Without `DATABASE_URL` the app uses the SQLite file `instance/rihla.db`. |
| [security.py](../security.py) | Back end | **Login, roles and CSRF.** `login_user()` / `logout_user()` write the signed session cookie, `load_current_user()` finds the logged-in user before every request, `@role_required(...)` protects pages, `csrf_token()` / `check_csrf()` block fake forms. |
| [validators.py](../validators.py) | Back end | **Server-side form checks** for login, sign-up, guide profile and reviews. Each function returns `(errors, cleaned)`. |
| [blueprints/public.py](../blueprints/public.py) | Back end | Pages for everyone: homepage, countries list with filters, country page, guide profile, photo credits, and the JSON API `/api/estimate` used by the calculator. |
| [blueprints/auth.py](../blueprints/auth.py) | Back end | **Sign up, log in, log out** (traveler sign-up and guide sign-up). |
| [blueprints/traveler.py](../blueprints/traveler.py) | Back end | Traveler pages: trip basket, checkout (simulated payment), My Trips, cancel a trip, rate a guide. |
| [blueprints/guide.py](../blueprints/guide.py) | Back end | Guide pages: dashboard (earnings, bookings, reviews) and profile editing. |
| [blueprints/admin.py](../blueprints/admin.py) | Back end | Admin pages: dashboard with commission totals, approve / reject guides, add / edit / delete content, all bookings, commission setting. |
| [blueprints/admin_resources.py](../blueprints/admin_resources.py) | Back end | Describes the 5 kinds of content the admin can manage (countries, monuments, restaurants, stays, flights): their form fields, how to check them, and when deleting is not allowed. One generic set of admin pages works for all 5. |
| [services/booking.py](../services/booking.py) | Back end | **The only booking code.** `create_booking()` checks the trip rules, reserves seats, calculates the commission and saves the booking; `cancel_booking()` cancels and gives the seats back. |
| [services/pricing.py](../services/pricing.py) | Back end | Money: commission split, trip cost estimate, `$` formatting, dollars → cents. |
| [services/search.py](../services/search.py) | Back end | Read-only queries: countries, flights, stays, approved guides with their average rating, the country search with filters. |
| [services/basket.py](../services/basket.py) | Back end | The trip basket, stored in the session cookie (ids and quantities only, never prices). |
| [services/reviews.py](../services/reviews.py) | Back end | Who may review a guide, and saving the review. |

### Database

| File | Part | What it does |
|---|---|---|
| [models.py](../models.py) | Database | **The 11 tables written as Python classes** (SQLAlchemy models): `User`, `GuideProfile`, `Country`, `Monument`, `Restaurant`, `Stay`, `Flight`, `Booking`, `BookingItem`, `Review`, `Setting`. Columns, relationships and CHECK rules are here. |
| [extensions.py](../extensions.py) | Database | Creates the `db` object (Flask-SQLAlchemy) and switches on SQLite's foreign-key checks. |
| [seed.py](../seed.py) | Database | **Sample data** loaded by `flask --app app init-db`: 6 countries with entry rules, monuments, restaurants, stays, flights from Beirut, guides, travelers, bookings and reviews. Also defines the 3 test accounts. |
| [photos.py](../photos.py) | Database | The real photos (Wikimedia Commons links) with each author and licence, used by `seed.py`. |
| [database/schema.sql](../database/schema.sql) | Database | The SQL `CREATE TABLE` statements of the 11 tables, exported from `models.py`. For reading; the app creates the tables itself. |
| `instance/rihla.db` | Database | The SQLite database file itself. Created by `init-db`, **not on GitHub** (generated). |

### Front end (HTML, CSS, JavaScript)

| File | Part | What it does |
|---|---|---|
| [templates/layout.html](../templates/layout.html) | Front end | **The frame of every page**: `<head>` (Bootstrap, fonts, our CSS), the navigation bar (links change with the role), flash messages, footer, scripts. Every other page starts with `{% extends "layout.html" %}`. |
| [templates/public/](../templates/public/) | Front end | `home.html` (hero + boarding-pass search + destinations), `countries.html` (list + filters), `country.html` (one country: passport card, photos, monuments, food, stays, flights, guides, calculator), `guide.html` (guide profile), `credits.html` (photo credits). |
| [templates/auth/](../templates/auth/) | Front end | `login.html`, `register.html` (traveler sign-up), `register_guide.html` (guide sign-up). |
| [templates/traveler/](../templates/traveler/) | Front end | `basket.html`, `checkout.html`, `trips.html` (My Trips with the "BOOKED" stamp), `review.html`. |
| [templates/guide/](../templates/guide/) | Front end | `dashboard.html`, `profile.html`. |
| [templates/admin/](../templates/admin/) | Front end | `dashboard.html`, `guides.html`, `list.html` + `form.html` (generic content pages), `bookings.html`, `settings.html`, `_nav.html` (admin tabs). |
| [templates/partials/](../templates/partials/) | Front end | Reusable pieces (Jinja macros): `forms.html` (form field with error message), `cards.html` (destination postcard, guide card), `passport.html` (entry badge), `book.html` (Add to trip form). |
| [templates/error.html](../templates/error.html) | Front end | The friendly 400 / 403 / 404 page. |
| [static/css/style.css](../static/css/style.css) | Front end | **All our styling**: colour variables (Lebanese flag palette), fonts, boarding-pass search, postcards, passport card, trip tickets, admin tables, responsive rules (`@media`). Loaded after Bootstrap so it wins. |
| [static/js/main.js](../static/js/main.js) | Front end | Small effects on every page: cards fade in when scrolled into view (IntersectionObserver), success messages close after 6 seconds. |
| [static/js/calculator.js](../static/js/calculator.js) | Front end | The **live trip-cost calculator** on the country page: on every change it calls `/api/estimate` with `fetch()` and draws the receipt. |

### Tests, settings and documents

| File | What it does |
|---|---|
| [tests/](../tests/) | **60 automated tests** (Python's built-in `unittest`). `base.py` gives every test a fresh copy of the sample data in a temporary database. Run: `.venv\Scripts\python -m unittest -v` |
| [requirements.txt](../requirements.txt) | The 4 Python packages to install: Flask, Flask-SQLAlchemy, python-dotenv, gunicorn. |
| [.env.example](../.env.example) | Template of the `.env` file (secret key). The real `.env` is never committed. |
| [.gitignore](../.gitignore) | Files Git must not upload: `.venv/`, `.env`, `instance/` (the database), caches. |
| [README.md](../README.md) | Project presentation, setup, test logins, Render deployment. |
| [docs/VISA_RESEARCH.md](VISA_RESEARCH.md) | Sources for the entry rules, popularity and direct flights. |
| [docs/PLAN.md](PLAN.md) | The original design plan. |

---

## 3. The database: 11 tables

| Table | Holds | Linked to |
|---|---|---|
| `users` | Everyone who can log in: name, email (unique), password **hash**, role (`traveler`, `guide`, `admin`) | — |
| `guide_profiles` | A guide's country, languages, bio, price per day, status (`pending`, `approved`, `rejected`) | `users` (one-to-one), `countries` |
| `countries` | Name, description, entry rules for a Lebanese passport, max stay, popularity, photo | — |
| `monuments`, `restaurants`, `stays` | Places in a country, with prices | `countries` |
| `flights` | Round trips from Beirut: dates, price per seat, `seats_total`, `seats_available` | `countries` |
| `bookings` | One trip: traveler, dates, total, commission rate used, commission, amount owed to providers, status | `users` |
| `booking_items` | The lines of a trip (a flight, a stay or a guide) with quantity and prices | `bookings`, and `flights` / `stays` / `guide_profiles` |
| `reviews` | 1-5 stars + comment for a guide, one per booked guide line | `booking_items`, `guide_profiles`, `users` |
| `settings` | Key / value settings, e.g. the commission rate | — |

Money is always stored in **whole cents** (`12.50` dollars → `1250`), so there are no rounding errors.

---

## 4. All the URLs (routes)

| URL | Function | Who can open it |
|---|---|---|
| `/` | `public.home` | Everyone |
| `/countries`, `/countries/<slug>` | `public.countries`, `public.country` | Everyone |
| `/guides/<id>`, `/credits` | `public.guide_profile`, `public.credits` | Everyone |
| `/api/estimate` | `public.api_estimate` (JSON for the calculator) | Everyone |
| `/register`, `/register/guide`, `/login` | `auth.register`, `auth.register_guide`, `auth.login` | Visitors |
| `/logout` (POST) | `auth.logout` | Logged-in users |
| `/me/basket`, `/me/basket/add`, `/me/basket/update`, `/me/basket/remove/<type>` | `traveler.basket_*` | Travelers |
| `/me/checkout`, `/me/trips`, `/me/trips/<id>/cancel`, `/me/trips/review/<id>` | `traveler.checkout`, `trips`, `cancel`, `review` | Travelers |
| `/guide/dashboard`, `/guide/profile` | `guide.dashboard`, `guide.profile` | Guides |
| `/admin/`, `/admin/guides`, `/admin/content/<kind>`, `/admin/bookings`, `/admin/settings` | `admin.*` | Admin |

---

## 5. Questions we expect, with the answers

### Accounts and security

**Where is the code that lets someone sign up?**
- The page (form): [templates/auth/register.html](../templates/auth/register.html). It is a normal HTML `<form method="post">` with a hidden CSRF token.
- The Python code: [blueprints/auth.py → `register()`](../blueprints/auth.py#L53) (line 53).
  1. `validate_registration()` in [validators.py](../validators.py#L52) checks the name, the email format, and the password (8+ characters, a letter and a number, both passwords equal).
  2. `_email_taken()` checks the email is not used yet.
  3. A `User` is created with role `traveler`, `user.set_password()` stores only the **hash**, and `db.session.commit()` saves it.
  4. `login_user()` logs the new user in and redirects to the homepage.
- Guide sign-up is [`register_guide()`](../blueprints/auth.py#L83) (line 83): it also creates a `GuideProfile` with status **`pending`**, so the guide is invisible until an admin approves.

**Where is the log-in code?**
[blueprints/auth.py → `login()`](../blueprints/auth.py#L17) (line 17). It validates the form, looks up the user by email, checks the password with `user.check_password()`, then calls `login_user()` from [security.py](../security.py#L31) which stores `user_id` in the session. "No such email" and "wrong password" show the **same** message, so nobody can find out which emails have an account.

**And log-out?**
[blueprints/auth.py → `logout()`](../blueprints/auth.py#L46) (line 46). It only accepts **POST** with the CSRF token (the "Log out" button in `layout.html` is a small form), so a link on another website cannot log you out. It calls `session.clear()`.

**How are passwords stored?**
Never in plain text. [models.py → `User.set_password()` / `check_password()`](../models.py#L60) (lines 60-70) use Werkzeug's `generate_password_hash` (scrypt, with a random **salt**, so two equal passwords give different hashes) and `check_password_hash`.

**How does the site remember who is logged in?**
With Flask's **session**: a cookie signed with `SECRET_KEY` ([config.py](../config.py)). We store only `user_id`. Before every request, [security.py → `load_current_user()`](../security.py#L43) (line 43) reloads the user from the database into `g.user`. It is registered in [app.py](../app.py) with `app.before_request(...)`.

**How do you stop a traveler from opening the admin pages?**
The decorator [security.py → `role_required()`](../security.py#L73) (line 73), placed above each protected route, e.g. `@role_required("admin")` in [blueprints/admin.py](../blueprints/admin.py#L29). Not logged in → redirected to the login page; wrong role → **403 Forbidden**.

**What is CSRF and how do you prevent it?**
Cross-Site Request Forgery: another website secretly submitting a form to our site while you are logged in. Every form contains a hidden random token (`{{ csrf_token() }}`), also kept in the session. [security.py → `check_csrf()`](../security.py#L109) (line 109) refuses any POST whose token is missing or different (400 error).

**Where is the form validation? Client side or server side?**
Both. The browser checks `required`, `minlength`, `type="email"` (HTML attributes in the templates), but these can be skipped, so the **server always checks again** in [validators.py](../validators.py). Error messages are shown under each field by the macro in [templates/partials/forms.html](../templates/partials/forms.html).

**How do you protect against SQL injection and XSS?**
- SQL injection: every query goes through SQLAlchemy with bound parameters (e.g. `db.select(User).filter_by(email=...)`); we never build SQL from strings.
- XSS: Jinja escapes every `{{ value }}` automatically, and our JavaScript writes text with `textContent`, never `innerHTML` ([static/js/calculator.js](../static/js/calculator.js)).

**After login, how does a user land on the right page?**
[security.py → `HOME_FOR_ROLE`](../security.py#L21): travelers go to My Trips, guides to their dashboard, the admin to the admin dashboard. A `?next=` link is only followed if it stays on our site (`is_safe_next_url()`, line 58), to avoid "open redirects".

### Database

**Which database do you use, and where are the tables defined?**
SQLite, through Flask-SQLAlchemy (the course stack). The tables are Python classes in [models.py](../models.py). The SQL version is in [database/schema.sql](../database/schema.sql).

**How is the database created?**
`flask --app app init-db` runs [app.py → `init_db()`](../app.py#L80): it drops every table, `db.create_all()` creates the 11 tables from `models.py`, then [seed.py → `seed_database()`](../seed.py#L349) inserts the sample data.

**Why are prices stored in cents?**
Decimal numbers like 0.1 are not exact in a computer. Whole cents (integers) are exact; `format_money()` in [services/pricing.py](../services/pricing.py#L75) shows them as `$12.50`.

**What are the relationships?**
One user → many bookings; one booking → many booking items; each booking item is a flight, a stay or a guide; one country → many monuments, restaurants, stays, flights and guides; one user ↔ one guide profile. They are written with `db.ForeignKey` and `db.relationship` in [models.py](../models.py). SQLite's foreign-key checks are switched on in [extensions.py](../extensions.py).

### Booking, commission and business rules

**Where is the booking code?**
In one place: [services/booking.py → `create_booking()`](../services/booking.py#L107) (line 107). The checkout route [blueprints/traveler.py → `checkout()`](../blueprints/traveler.py#L104) (line 104) calls it. Either everything is saved, or nothing (`db.session.rollback()` on any error).

**How is the commission calculated?**
[services/pricing.py → `split_commission()`](../services/pricing.py#L17) (line 17): commission = line total × rate / 100, rounded with `Decimal` (half up), provider share = total − commission, so the two always add up exactly. The rate (10% by default) is stored in the `settings` table and can be changed by the admin ([blueprints/admin.py → `settings()`](../blueprints/admin.py#L211)). Each booking keeps a **copy** of the rate it was charged.

**How do you make sure a flight is never overbooked?**
[services/booking.py → `_reserve_seats()`](../services/booking.py#L41) (line 41) runs one conditional SQL update:
`UPDATE flights SET seats_available = seats_available - n WHERE id = ? AND seats_available >= n`.
If two people take the last seat at the same moment, only one update can succeed.

**What happens when a trip is cancelled?**
[services/booking.py → `cancel_booking()`](../services/booking.py#L170) (line 170): only the owner, only before the trip starts; the seats are given back and the status becomes `cancelled`.

**Where is the trip basket stored?**
In the session cookie ([services/basket.py](../services/basket.py)), like a shopping cart. Only ids and quantities are stored; prices are always read again from the database, so nobody can change a price.

**Is the payment real?**
No. The checkout ([templates/traveler/checkout.html](../templates/traveler/checkout.html)) is **simulated**: the traveler ticks "I understand this is a simulated payment" and no card is asked.

**Who can rate a guide?**
Only a traveler who booked that guide, after the trip has ended, once per booking: [services/reviews.py → `review_problem()`](../services/reviews.py#L19) (line 19). The guide's star rating is the average of those reviews ([models.py → `GuideProfile.average_rating()`](../models.py#L94)).

**How does a new guide become visible?**
They sign up with status `pending`. The admin approves them in [blueprints/admin.py → `set_guide_status()`](../blueprints/admin.py#L90) (line 90). Public pages only show guides with status `approved` ([services/search.py](../services/search.py#L79), line 79).

**How does the search with filters work?**
The homepage "boarding pass" is a GET form, so the filters go into the URL (`/countries?month=3&budget=1500`). [blueprints/public.py → `countries()`](../blueprints/public.py#L43) reads them and calls [services/search.py → `search_countries()`](../services/search.py#L99), which estimates each country's trip price and sorts warm, popular and cheap countries first.

**How does the admin add or edit a country, flight, etc.?**
One set of generic routes in [blueprints/admin.py](../blueprints/admin.py#L119) (`content_list`, `content_form`, `content_delete`) uses the descriptions in [blueprints/admin_resources.py](../blueprints/admin_resources.py). Deleting something already booked is refused (`delete_problem()`).

### Front end and design

**Which fonts do you use?**
Two Google Fonts, loaded in [templates/layout.html](../templates/layout.html) (line 16):
- **Fraunces** (a serif) for titles: `--font-display` in [static/css/style.css](../static/css/style.css#L23) (line 23).
- **Inter** (a clean sans-serif) for body text: `--font-body` (line 24).
If they cannot load, the browser falls back to Georgia / the system font.

**Which colours, and why?**
The Lebanese flag: red `#EE161F`, cedar green `#00A651`, white. They are CSS variables at the top of [static/css/style.css](../static/css/style.css#L10) (lines 10-24), e.g. `--red`, `--cedar`, `--snow`. Darker shades are used for buttons so the text has enough contrast (accessibility).

**Did you use a CSS framework?**
Bootstrap 5.3 from a CDN ([layout.html](../templates/layout.html), line 13 for the CSS, and the JS bundle at the bottom) for the grid, navbar, forms and alerts. Our own `style.css` is loaded after it, so our design wins.

**How is the site responsive (phone)?**
Bootstrap's grid classes (`col-lg-6`, `col-md-3`...), the navbar that collapses into a ☰ menu below 992 px, and our own `@media` rules in [style.css](../static/css/style.css) (from line 538). The viewport meta tag is in `layout.html` (line 5).

**Where are the navbar and footer? Why don't you repeat them on every page?**
They are written once in [templates/layout.html](../templates/layout.html). Each page uses **template inheritance**: `{% extends "layout.html" %}` and fills `{% block content %}`. The navbar shows different links for visitors, travelers, guides and the admin.

**Where is the JavaScript and what does it do?**
Two files: [static/js/main.js](../static/js/main.js) (scroll animations, auto-closing messages) and [static/js/calculator.js](../static/js/calculator.js) (the live calculator). The site still works without JavaScript; only the calculator needs it.

**How does the calculator get the price without reloading the page?**
[calculator.js](../static/js/calculator.js) calls `fetch("/api/estimate?...")` (AJAX). The server route [blueprints/public.py → `api_estimate()`](../blueprints/public.py#L108) answers in **JSON** using the same `estimate_trip_cost()` as the rest of the site, so the price is always the same everywhere.

**Where do the photos come from?**
Real photographs from Wikimedia Commons (free licences), listed with their authors in [photos.py](../photos.py) and shown on the `/credits` page. No image is AI-generated.

### Running and deployment

**How do I run the project on my computer?**
See the README: create the virtual environment, `pip install -r requirements.txt`, `flask --app app init-db`, `flask --app app run --debug`, open http://127.0.0.1:5000.

**Which accounts can I use?**
`traveler@rihla.test` / `Traveler123!`, `guide@rihla.test` / `Guide123!`, `admin@rihla.test` / `Admin123!` (fake accounts from [seed.py](../seed.py#L27)).

**How is the site put online?**
On Render (free Web Service): build command `pip install -r requirements.txt && flask --app app init-db`, start command `gunicorn app:app`, and a `SECRET_KEY` environment variable. Gunicorn is a production web server; `flask run` is only for development.

**How do you know the code works?**
60 automated tests in [tests/](../tests/) check sign-up, login, roles, CSRF, booking rules, seats, commission, reviews and admin pages. Each test runs on a fresh temporary copy of the sample data.

**Did the site have an AI agent?**
An AI chat was built during development, then removed from the final version to keep the project within the course tools. All booking is done through the website pages.
