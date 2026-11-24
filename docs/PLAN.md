# Rihla — Project Plan (Flask version)

> *"From the first click to the last dinner."*
> GIN446 Web — Final Project. Status: **waiting for approval** (no code written yet).

---

## 0. Stack and why

The stack matches what the course taught (Chapter 9 + the Flask lab in `Server-side/fulllab`).

| Layer | Choice | Why |
|---|---|---|
| Front end | HTML5, CSS3, vanilla JS, **Bootstrap 5** | Bootstrap gives the responsive grid; our own `style.css` gives the brand look. |
| Templates | **Jinja2** (comes with Flask) | `layout.html` + `{% extends %}` like the lab, so header/footer/chat button are written once. |
| Back end | **Python 3.12 + Flask 3** | Taught in Chapter 9. **Blueprints** (also in Chapter 9) split the app by role. |
| Database | **SQLite via Flask-SQLAlchemy** | Exactly the Chapter 9 pattern: `DATABASE_URL` env var, falls back to `sqlite:///rihla.db`. One file, nothing to install. Works unchanged with PostgreSQL on Render. |
| Passwords | `werkzeug.security` `generate_password_hash` / `check_password_hash` | Werkzeug is already installed with Flask — no extra library. |
| Sessions | Flask's built-in `session` (signed cookie, `SECRET_KEY`) | Built in. |
| SQL injection | SQLAlchemy queries always use bound parameters | We never build SQL by gluing strings. |
| Validation | Our own `validators.py` returning `(errors, cleaned)` | Same pattern as the lab's `validate_profile()`. |
| CSRF | A small hand-written token stored in `session` | Avoids adding Flask-WTF. |
| AI calls | Python's built-in `urllib.request` | Talks to the provider's HTTP API; no SDK. Provider chosen later in `.env` (`AI_PROVIDER=claude|openai|none`). |
| Deploy (optional) | Render + `gunicorn app:app` | Same as the lab. |
| Tools | VS Code, Git, GitHub, `py` launcher / venv | |

`requirements.txt`: `Flask`, `Flask-SQLAlchemy`, `gunicorn`, and **`python-dotenv`** (needs your OK — it loads `.env` into environment variables; alternative is setting env vars by hand in the terminal).

---

## 1. Brand names

1. **Rihla** — *"From the first click to the last dinner."* (رحلة = journey) ⭐
2. **Compass & Fork** — *"Where to go. What to eat. All booked."*
3. **Cedar Passport** — *"Fly from Beirut, land everywhere."*
4. **Wayfare** — *"Every trip, from takeoff to supper."*
5. **Atlas & Olive** — *"The whole journey, planned in one place."*

---

## 2. Pages (routes) by role

**Public** — blueprint `public`, `auth`
| Route | Template | Purpose |
|---|---|---|
| `/` | `public/index.html` | Hero, boarding-pass search, featured countries, AI teaser |
| `/countries` | `public/countries.html` | Postcard grid + filters (month, budget, interests) |
| `/countries/<slug>` | `public/country.html` | Tabs: Overview · Monuments · Food · Stays · Flights · Guides · **Cost calculator** |
| `/guides/<id>` | `public/guide.html` | Guide bio, languages, price, reviews |
| `/login`, `/logout` | `auth/login.html` | One login for all roles → redirect by role |
| `/register` | `auth/register.html` | Traveler sign-up |
| `/register/guide` | `auth/register_guide.html` | Guide sign-up → status **pending** |

**Traveler** — blueprint `traveler`, prefix `/me`, every route `@role_required("traveler")`
| Route | Purpose |
|---|---|
| `/me/basket` (+ POST `/me/basket/add`, `/me/basket/remove`) | Trip basket (kept in `session`) with live total |
| `/me/checkout` | **Simulated** checkout: summary + "Pay (simulated)" — no card fields |
| `/me/trips` | Upcoming / past trips, Cancel, "Rate your guide" |
| `/me/trips/<item_id>/review` | Stars + comment (only if booked that guide **and** trip ended) |
| 💬 chat panel | Floating button on every page (logged-in travelers) |

**Guide** — blueprint `guide`, prefix `/guide`
| Route | Purpose |
|---|---|
| `/guide/dashboard` | Approval status, bookings, average rating, earnings (after commission) |
| `/guide/profile` | Edit country, languages, bio, daily price |

**Admin** — blueprint `admin`, prefix `/admin`
| Route | Purpose |
|---|---|
| `/admin/` | Stats: bookings, revenue, **commission earned**, pending guides |
| `/admin/guides` | Approve / reject |
| `/admin/<resource>` for countries, monuments, restaurants, stays, flights | List + add / edit / delete |
| `/admin/bookings` | All bookings, filters |
| `/admin/settings` | Commission % (default 10) |

**Chat API** — blueprint `agent`, prefix `/api` (JSON, like the lab's `ex4-json-api`)
| Route | Purpose |
|---|---|
| POST `/api/chat` | Send a message, get reply + cards |
| POST `/api/confirm/<proposal_id>` | The "Confirm" button |
| GET `/api/conversations`, `/api/conversations/<id>` | Resume old chats |

**Role protection** — one decorator, easy to explain:
```python
@traveler_bp.route("/trips")
@role_required("traveler")      # not logged in / wrong role → redirect to /login
def my_trips(): ...
```

---

## 3. Database (SQLAlchemy models → SQLite tables)

### Diagram
```
                 ┌──────────────┐
                 │    User      │ role: traveler | guide | admin
                 └──────┬───────┘
        ┌───────────────┼────────────────────┬──────────────────────┐
        │1:1            │1:N                 │1:N                   │1:N
┌───────▼───────┐ ┌─────▼──────┐   ┌─────────▼────────┐   ┌─────────▼────────┐
│ GuideProfile  │ │  Booking   │   │ ChatConversation │   │ BookingProposal  │
└───┬───────────┘ └─────┬──────┘   └─────────┬────────┘   └──────────────────┘
    │N:1               │1:N                  │1:N
    │            ┌─────▼───────┐     ┌───────▼──────┐
    │            │ BookingItem │     │ ChatMessage  │
    │            └─┬────┬────┬─┘     └──────────────┘
    │   flight_id ─┘ stay_id └─ guide_id ──► GuideProfile
    │              │    │                ┌──────────┐
┌───▼─────────┐    │    │                │  Review  │──► BookingItem (1:1)
│   Country   │◄───┴────┴── Flight, Stay,└──────────┘
└─────────────┘             Monument, Restaurant (all N:1)     Setting (key/value)
```

### Tables (SQLAlchemy column types)

**users** — `id` Integer PK · `full_name` String(100) · `email` String(150) unique · `password_hash` String(255) · `role` String(10) (`traveler`/`guide`/`admin`) · `created_at` DateTime

**countries** — `id` · `name` String(80) · `slug` String(80) unique · `description` Text · `best_time` String(100) · `currency` String(50) · `language` String(50) · `warm_months` String(40) e.g. `"3,4,5,6"` · `tags` String(150) e.g. `"beach,history,food"` · `avg_daily_spend` Numeric(8,2) · `hero_image` String(255)

**monuments** — `id` · `country_id` FK · `name` · `city` · `description` Text · `entry_cost` Numeric(8,2) · `image`

**restaurants** — `id` · `country_id` FK · `name` · `city` · `must_try_dish` · `description` · `price_range` String(3) (`$`/`$$`/`$$$`) · `avg_meal_cost` Numeric(8,2) · `image`

**stays** — `id` · `country_id` FK · `name` · `type` (`hotel`/`apartment`) · `city` · `price_per_night` Numeric(8,2) · `rating` Numeric(2,1) · `image`

**flights** — `id` · `country_id` FK (destination) · `airline` · `from_city` (seed: "Beirut") · `to_city` · `depart_date` Date · `return_date` Date · `price` Numeric(8,2) per seat · `seats_total` Integer · `seats_available` Integer

**guide_profiles** — `id` · `user_id` FK unique · `country_id` FK · `languages` String(150) · `bio` Text · `price_per_day` Numeric(8,2) · `status` (`pending`/`approved`/`rejected`, default `pending`)
→ Star rating is **computed** with `func.avg(Review.rating)`, never stored, so it can't go out of sync.

**bookings** (one trip) — `id` · `traveler_id` FK · `start_date` · `end_date` · `total_price` · `commission_rate` (copy of the rate *at booking time*) · `commission_amount` · `provider_amount` · `status` (`confirmed`/`cancelled`) · `source` (`web`/`agent`) · `created_at`

**booking_items** — `id` · `booking_id` FK · `item_type` (`flight`/`stay`/`guide`) · `flight_id` / `stay_id` / `guide_id` nullable FKs (exactly one set) · `quantity` (seats / nights / days) · `unit_price` · `line_total` · `commission_amount` · `provider_amount`

**reviews** — `id` · `booking_item_id` FK **unique** · `guide_id` FK · `traveler_id` FK · `rating` Integer 1–5 · `comment` Text · `created_at`

**settings** — `key` String PK · `value` String (e.g. `commission_rate = "10"`)

**chat_conversations** — `id` · `user_id` FK · `title` · `created_at` · `updated_at`

**chat_messages** — `id` · `conversation_id` FK · `role` (`user`/`assistant`/`tool`) · `content` Text · `cards_json` Text nullable · `created_at`
→ Rate limit = count of this user's `role="user"` messages in the last hour.

**booking_proposals** ⭐ — `id` · `user_id` FK · `action` (`create`/`cancel`) · `payload_json` Text · `total_price` · `status` (`pending`/`confirmed`/`expired`) · `created_at` (expires after 15 min)
→ The AI **cannot book**. `create_booking` only saves a proposal; the real booking happens when the logged-in user clicks **Confirm**.

> **Change made in Step 1:** every money column is stored as an **Integer number of cents**
> (`price_cents`, `total_cents`…; $12.50 → 1250) instead of `Numeric(8,2)`. SQLite has no exact
> decimal type, so SQLAlchemy would store decimals as floats and warn about rounding errors.
> Whole cents are always exact. Templates show them with the `|money` filter.

### Commission math (per item, with Python `Decimal` to avoid float rounding errors)
```
line_total        = unit_price × quantity
commission_amount = round(line_total × rate / 100, 2)
provider_amount   = line_total − commission_amount
```

### Create + seed (the Chapter 9 pattern: configure → create → seed)
- `flask --app app init-db` → `db.create_all()` + inserts seed data (custom Flask CLI command).
- Seed: **Turkey, Armenia, Egypt, Jordan, Georgia, Malaysia**: countries a Lebanese passport can enter with no visa arranged in advance (changed from Italy, Japan, Greece and Thailand, which need visas; see `docs/VISA_RESEARCH.md`). Each has real monuments, dishes, restaurants, stays, flights from Beirut, approved + pending guides, past and upcoming bookings, reviews, and one test account per role.
- `countries` also stores the entry rules for a Lebanese passport: `entry_type` (visa_free / visa_on_arrival / conditional / evisa), `max_stay`, `entry_notes`, `popularity` (1-5) and `popularity_note`.
- `database/schema.sql` is exported from the real SQLite file so the instructor can read the tables as SQL.

---

## 4. AI agent

```
[chat.js] ──fetch POST──► /api/chat      (blueprints/agent.py)
                           1. logged in as traveler?
                           2. rate limit (e.g. 20 msgs/hour)
                           3. save user message
                           4. text is "confirm" + pending proposal? → confirm directly (no AI)
                                      │
                        AI_PROVIDER set in .env?
               ┌──────────yes──────────┴──────────no──────────┐
        agent/ai_client.py                          agent/demo_agent.py
        (history + tool schemas → provider          (keyword rules: "flights to Italy",
         via urllib; loop max 5 tool rounds)          "cheapest hotel in Japan" …)
               │ model asks for a tool                        │
               ▼                                              ▼
            agent/tools.py  run_tool(name, args, user_id)
               │  user_id ALWAYS from session, never from the AI
               ▼
   services/search.py · services/pricing.py · services/booking.py
               │            (same functions the normal web pages use)
               ▼
            SQLite (Flask-SQLAlchemy)
```

| Tool | Calls | Notes |
|---|---|---|
| `search_countries(month, budget, days, interests)` | `search.py` | uses `warm_months`, `tags`, estimated cost |
| `get_country_details(country)` | `search.py` | monuments, food, top stays |
| `search_flights(from_city, to_country, date)` | `search.py` | seats > 0 only |
| `search_hotels(country, check_in, nights, max_price)` | `search.py` | |
| `list_guides(country, language, max_price)` | `search.py` | approved only, with avg rating |
| `estimate_trip_cost(flight_id, stay_id, nights, guide_id, days)` | `pricing.py` | same calculator as the country page |
| `create_booking(items)` | **proposal only** | returns summary card + Confirm button |
| `list_my_bookings()` | `booking.py` | current user only |
| `cancel_booking(booking_id)` | **proposal only** | checks ownership |

Both modes return the **same JSON shape** `{reply, cards[], proposal?}`, so `chat.js` doesn't care which answered — demo mode is a safe fallback for the presentation.

---

## 5. Folder structure
```
Final Project/rihla/
├─ app.py                ← create_app(): config, db, blueprints, CLI init-db
├─ config.py             ← reads SECRET_KEY, DATABASE_URL, AI_* from env
├─ extensions.py         ← db = SQLAlchemy()
├─ models.py             ← all tables as classes
├─ seed.py               ← sample data + test accounts
├─ validators.py         ← form checks, (errors, cleaned) like the lab
├─ security.py           ← login_user(), role_required, CSRF token
├─ services/
│  ├─ search.py
│  ├─ pricing.py
│  └─ booking.py         ← create_booking(), cancel_booking(): the ONLY booking code
├─ agent/
│  ├─ tools.py           ← tool schemas + run_tool()
│  ├─ ai_client.py       ← provider adapter (Claude / OpenAI)
│  └─ demo_agent.py      ← rule-based fallback
├─ blueprints/
│  ├─ public.py  auth.py  traveler.py  guide.py  admin.py  agent.py
├─ templates/
│  ├─ layout.html        ← navbar, footer, chat widget, flash messages
│  ├─ partials/  public/  auth/  traveler/  guide/  admin/
├─ static/
│  ├─ css/style.css
│  ├─ js/main.js  calculator.js  chat.js
│  └─ img/
├─ database/schema.sql   ← exported for the report
├─ instance/rihla.db     ← the SQLite file (NOT committed)
├─ requirements.txt
├─ .env.example          ← committed, empty values
├─ .env                  ← NOT committed (SECRET_KEY, AI key)
├─ .gitignore            ← .venv/, __pycache__/, .env, instance/
└─ README.md
```

Run (same as the lab):
```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask --app app init-db
flask --app app run --debug      → http://127.0.0.1:5000/
```

---

## 6. Visual style

**Mood:** vintage travel posters × modern travel magazine, in the colours of the **Lebanese flag**
(the trips start in Beirut): red and white, with the green of the cedar.

> **Changed after Step 8:** the original warm palette (midnight blue, sand, terracotta, olive,
> saffron) was replaced by the flag palette below.

| Role | Color | Hex | Contrast |
|---|---|---|---|
| Flag red: ribbon, icons, highlights | Lebanese red | `#EE161F` | decoration only |
| Buttons and links (white text) | Deep red | `#D7141C` | 5.2:1 |
| Cedar: badges, decoration | Cedar green | `#00A651` | decoration only |
| Green buttons (white text) | Deep cedar | `#00753A` | 5.8:1 |
| Headings, dark bars, footer | Very dark cedar | `#10291D` | 14.5:1 |
| Background | Flag white | `#F8F8F6` | |
| Stars only | Gold | `#F2C14E` | |
| Body text | Charcoal | `#222826` | |

The bright flag colours fail the WCAG AA 4.5:1 minimum behind small white text (red 4.4:1, green 3.2:1),
so the deeper shades are used for buttons.

**Fonts:** Fraunces (headings) + Inter (body), from Google Fonts.

**Signature details:** a red / white / red flag ribbon under the menu · login poster with a cedar 🌲 in a white
circle · boarding-pass booking cards with a perforated stub · postcard country cards with a stamp ·
"postmark" animation on confirmed trips.

**Homepage:** hero photo + headline + boarding-pass search widget → "Pick your next stamp" postcards → How it works (Fly → Stay → Explore → Eat) → AI agent teaser → top guides → footer with image credits.

---

## 7. Open questions

1. Brand name: Rihla, or another?
2. OK to add `python-dotenv` and Google Fonts?
3. Commission taken **out of the provider's share** (traveler pays listed price), or **added on top**?
4. Reviews only after the trip end date, once per booked guide?
5. Later: your name (slides) and GitHub username / repo name.
