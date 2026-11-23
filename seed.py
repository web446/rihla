"""Sample data so the site looks full during the demo.

Run with:   flask --app app init-db
It DELETES all tables, creates them again, and inserts everything below.

Prices are realistic estimates in US dollars, written here in dollars and
turned into cents by usd(). Flights, hotel prices and bookings are SIMULATED.
Restaurants, monuments and most hotels are real places; the people (guides,
travelers) and the apartments are fictional.
"""
from datetime import date

from extensions import db
from models import (Country, Flight, GuideProfile, Monument, Restaurant, Review,
                    Setting, Stay, User)
from services.booking import create_booking

# ---------------------------------------------------------------------------
# Test accounts (also listed in README.md). These are fake, local-only logins.
# ---------------------------------------------------------------------------
TEST_ACCOUNTS = {
    "admin":    ("admin@rihla.test", "Admin123!"),
    "traveler": ("traveler@rihla.test", "Traveler123!"),
    "guide":    ("guide@rihla.test", "Guide123!"),
}


def usd(amount):
    """Dollars -> cents, e.g. usd(12.5) == 1250."""
    return int(round(amount * 100))


# ---------------------------------------------------------------------------
# Countries and everything inside them
# Each monument: (name, city, entry cost $, description)
# Each restaurant: (name, city, must-try dish, price range, avg meal $, description)
# Each stay: (name, type, city, $ per night, rating, description)
# Each flight: (airline, number, to_city, stops, depart, return, $ per seat, seats)
# ---------------------------------------------------------------------------
COUNTRIES = [
    {
        "name": "Italy", "slug": "italy",
        "tagline": "Ruins by day, carbonara by night.",
        "description": "Ancient Rome, Renaissance Florence, the canals of Venice and the pizza of "
                       "Naples. Italy packs three thousand years of history and the world's most "
                       "loved kitchen into one long, sunny peninsula.",
        "best_time": "April to June, September to October",
        "currency": "Euro (EUR)", "language": "Italian",
        "warm_months": "5,6,7,8,9", "tags": "history,food,art,city",
        "daily_spend": 90,
        "monuments": [
            ("Colosseum", "Rome", 20, "The 2,000-year-old amphitheatre where gladiators fought in front of 50,000 people."),
            ("Vatican Museums & Sistine Chapel", "Vatican City", 22, "Michelangelo's ceiling and one of the largest art collections on Earth."),
            ("Trevi Fountain", "Rome", 0, "Throw a coin over your shoulder and legend says you will return to Rome."),
            ("Leaning Tower of Pisa", "Pisa", 21, "Climb 251 steps up the world's most famous tilted bell tower."),
            ("Pompeii Archaeological Park", "Pompeii", 20, "A Roman city frozen in time by the eruption of Vesuvius in 79 AD."),
        ],
        "restaurants": [
            ("Roscioli Salumeria con Cucina", "Rome", "Spaghetti alla carbonara", "$$", 45, "A deli-meets-restaurant famous for its carbonara and cheese counter."),
            ("L'Antica Pizzeria da Michele", "Naples", "Pizza Margherita", "$", 10, "Serving only a few classic pizzas since 1870. Expect a queue."),
            ("All'Antico Vinaio", "Florence", "Schiacciata sandwich", "$", 9, "Giant focaccia sandwiches stuffed with salami, pecorino and truffle cream."),
            ("Trattoria Mario", "Florence", "Ribollita & bistecca", "$$", 30, "Lunch-only family trattoria by the San Lorenzo market, shared tables."),
        ],
        "stays": [
            ("Hotel Artemide", "hotel", "Rome", 220, 4.7, "Elegant Art Nouveau hotel on Via Nazionale with a rooftop terrace."),
            ("Hotel Santa Maria", "hotel", "Rome", 180, 4.6, "A quiet courtyard hotel in the heart of Trastevere."),
            ("Trastevere Rooftop Loft", "apartment", "Rome", 130, 4.8, "Sunny loft with a private terrace over terracotta roofs."),
            ("Duomo View Studio", "apartment", "Florence", 110, 4.5, "Small studio with a window facing Brunelleschi's dome."),
        ],
        "flights": [
            ("Middle East Airlines", "ME231", "Rome", "Direct", date(2026, 12, 18), date(2026, 12, 26), 480, 40),
            ("ITA Airways", "AZ825", "Rome", "Direct", date(2027, 3, 12), date(2027, 3, 19), 430, 36),
            ("Middle East Airlines", "ME231", "Rome", "Direct", date(2027, 4, 22), date(2027, 4, 29), 455, 40),
            ("Middle East Airlines", "ME233", "Milan", "Direct", date(2027, 6, 5), date(2027, 6, 13), 510, 30),
        ],
    },
    {
        "name": "Japan", "slug": "japan",
        "tagline": "Neon cities, quiet temples, perfect ramen.",
        "description": "From the neon streets of Tokyo to the wooden temples of Kyoto, Japan mixes "
                       "ultra-modern life with centuries-old tradition, and the food is worth the "
                       "flight on its own.",
        "best_time": "Late March to May (cherry blossoms), October to November",
        "currency": "Japanese Yen (JPY)", "language": "Japanese",
        "warm_months": "5,6,7,8,9", "tags": "culture,food,city,nature",
        "daily_spend": 100,
        "monuments": [
            ("Fushimi Inari Taisha", "Kyoto", 0, "Thousands of bright orange torii gates winding up a forest mountain."),
            ("Senso-ji Temple", "Tokyo", 0, "Tokyo's oldest temple, reached through the busy Nakamise shopping street."),
            ("Kinkaku-ji (Golden Pavilion)", "Kyoto", 3, "A Zen temple covered in gold leaf, reflected in a calm pond."),
            ("Himeji Castle", "Himeji", 7, "The best-preserved original castle in Japan, nicknamed the White Heron."),
            ("Tokyo Skytree", "Tokyo", 20, "A 634 m tower with views all the way to Mount Fuji on clear days."),
        ],
        "restaurants": [
            ("Ichiran Shibuya", "Tokyo", "Tonkotsu ramen", "$", 12, "Rich pork-bone ramen eaten in private solo booths."),
            ("Tsukiji Outer Market", "Tokyo", "Fresh sushi & tamagoyaki", "$$", 25, "Hundreds of stalls selling the freshest seafood in the city."),
            ("Nishiki Market", "Kyoto", "Street snacks & matcha sweets", "$", 15, "\"Kyoto's kitchen\": a covered street of pickles, tofu and sweets."),
            ("Gyukatsu Motomura", "Tokyo", "Gyukatsu (breaded beef)", "$$", 18, "Crispy beef cutlet you finish yourself on a tiny hot stone."),
        ],
        "stays": [
            ("Park Hotel Tokyo", "hotel", "Tokyo", 210, 4.5, "Art hotel on the upper floors of a Shiodome tower, with skyline views."),
            ("Hotel Gracery Shinjuku", "hotel", "Tokyo", 150, 4.3, "The \"Godzilla hotel\", right in the middle of Shinjuku's nightlife."),
            ("Kyoto Machiya Townhouse", "apartment", "Kyoto", 170, 4.9, "A restored wooden townhouse with tatami rooms and a small garden."),
            ("Asakusa Tatami Flat", "apartment", "Tokyo", 95, 4.4, "Simple flat with futons, five minutes from Senso-ji."),
        ],
        "flights": [
            ("Qatar Airways", "QR419", "Tokyo", "via Doha", date(2027, 3, 25), date(2027, 4, 5), 1180, 30),
            ("Emirates", "EK958", "Tokyo", "via Dubai", date(2027, 4, 10), date(2027, 4, 20), 1250, 30),
            ("Qatar Airways", "QR419", "Osaka", "via Doha", date(2027, 5, 14), date(2027, 5, 24), 1120, 24),
            ("Turkish Airlines", "TK827", "Tokyo", "via Istanbul", date(2027, 10, 8), date(2027, 10, 18), 1090, 28),
        ],
    },
    {
        "name": "Greece", "slug": "greece",
        "tagline": "Gods, islands and endless meze.",
        "description": "The birthplace of democracy and the Olympics, with white-and-blue island "
                       "villages, crystal water and some of the most relaxed food culture in the "
                       "Mediterranean, only a short flight from Beirut.",
        "best_time": "May to June, September to October",
        "currency": "Euro (EUR)", "language": "Greek",
        "warm_months": "5,6,7,8,9,10", "tags": "beach,history,islands,food",
        "daily_spend": 75,
        "monuments": [
            ("Acropolis & Parthenon", "Athens", 22, "The marble temple of Athena on a rock above the capital, built 2,400 years ago."),
            ("Delphi", "Delphi", 13, "The mountain sanctuary of the ancient oracle, \"the navel of the world\"."),
            ("Palace of Knossos", "Crete", 16, "The Bronze Age palace of the Minoans and the legend of the Minotaur."),
            ("Meteora Monasteries", "Kalambaka", 4, "Monasteries balanced on top of giant rock pillars."),
        ],
        "restaurants": [
            ("Thanasis", "Athens", "Kebab & souvlaki", "$", 10, "A Monastiraki classic since 1964, steps from the flea market."),
            ("Karamanlidika", "Athens", "Cured meats & meze", "$$", 25, "A deli-taverna serving Anatolian-Greek cured meats and cheeses."),
            ("Lucky's Souvlakis", "Santorini", "Pork gyros pita", "$", 6, "Tiny, cheap and loved by locals in Fira."),
            ("Ammoudi Fish Tavern", "Santorini", "Grilled octopus", "$$$", 55, "Seafood at the water's edge below Oia, watching the sunset."),
        ],
        "stays": [
            ("Hotel Grande Bretagne", "hotel", "Athens", 450, 4.8, "Historic luxury hotel on Syntagma Square with an Acropolis-view rooftop."),
            ("Herodion Hotel", "hotel", "Athens", 190, 4.6, "Boutique hotel at the foot of the Acropolis."),
            ("Plaka Acropolis-View Apartment", "apartment", "Athens", 120, 4.7, "Balcony breakfasts facing the Parthenon."),
            ("Oia Cave House", "apartment", "Santorini", 260, 4.9, "A whitewashed cave home carved into the caldera cliff."),
        ],
        "flights": [
            ("Aegean Airlines", "A3945", "Athens", "Direct", date(2027, 3, 5), date(2027, 3, 11), 320, 40),
            ("Middle East Airlines", "ME243", "Athens", "Direct", date(2027, 5, 20), date(2027, 5, 27), 350, 40),
            ("Aegean Airlines", "A3945", "Athens", "Direct", date(2027, 6, 18), date(2027, 6, 26), 380, 36),
        ],
    },
    {
        "name": "Turkey", "slug": "turkey",
        "tagline": "Two continents, one breakfast table.",
        "description": "Istanbul straddles Europe and Asia, Cappadocia floats in hot-air balloons "
                       "and Ephesus is one of the best-kept Roman cities in the world. Close, "
                       "affordable and full of flavour.",
        "best_time": "April to May, September to November",
        "currency": "Turkish Lira (TRY)", "language": "Turkish",
        "warm_months": "5,6,7,8,9,10", "tags": "history,food,city,culture",
        "daily_spend": 55,
        "monuments": [
            ("Hagia Sophia", "Istanbul", 27, "A 1,500-year-old cathedral-turned-mosque with a breathtaking dome."),
            ("Topkapi Palace", "Istanbul", 30, "Home of the Ottoman sultans for 400 years, with the treasury and harem."),
            ("Basilica Cistern", "Istanbul", 20, "An underground forest of 336 columns from the 6th century."),
            ("Ephesus", "Selcuk", 40, "Walk Roman streets to the Library of Celsus."),
            ("Goreme Open-Air Museum", "Cappadocia", 20, "Rock-cut churches painted with Byzantine frescoes."),
        ],
        "restaurants": [
            ("Karakoy Gulluoglu", "Istanbul", "Pistachio baklava", "$", 8, "The city's most famous baklava bakery, since 1820."),
            ("Ciya Sofrasi", "Istanbul", "Anatolian home cooking", "$$", 18, "Regional dishes from all over Turkey, on the Asian side in Kadikoy."),
            ("Hafiz Mustafa 1864", "Istanbul", "Turkish delight & kunefe", "$", 10, "A historic sweets shop for lokum and hot kunefe."),
            ("Pandeli", "Istanbul", "Lamb with eggplant puree", "$$$", 40, "Blue-tiled Ottoman restaurant above the Spice Bazaar."),
        ],
        "stays": [
            ("Pera Palace Hotel", "hotel", "Istanbul", 230, 4.6, "The 1892 hotel of the Orient Express travellers."),
            ("Sirkeci Mansion", "hotel", "Istanbul", 140, 4.7, "Friendly boutique hotel next to Gulhane Park."),
            ("Cappadocia Cave Suite", "apartment", "Cappadocia", 160, 4.8, "A cave room with a terrace to watch the morning balloons."),
            ("Galata Tower Loft", "apartment", "Istanbul", 85, 4.5, "Modern loft on a steep street below Galata Tower."),
        ],
        "flights": [
            ("Turkish Airlines", "TK827", "Istanbul", "Direct", date(2026, 12, 10), date(2026, 12, 15), 290, 45),
            ("Pegasus Airlines", "PC747", "Istanbul", "Direct", date(2027, 3, 18), date(2027, 3, 23), 250, 40),
            ("Middle East Airlines", "ME265", "Istanbul", "Direct", date(2027, 4, 15), date(2027, 4, 21), 310, 40),
            ("Turkish Airlines", "TK829", "Istanbul", "Direct", date(2027, 9, 9), date(2027, 9, 16), 300, 45),
        ],
    },
    {
        "name": "Egypt", "slug": "egypt",
        "tagline": "Five thousand years, still warm.",
        "description": "Stand in front of the last surviving Wonder of the Ancient World, sail the "
                       "Nile past Luxor's temples and snorkel the Red Sea. Egypt is warm almost all "
                       "year and one of the best-value trips from Beirut.",
        "best_time": "October to April",
        "currency": "Egyptian Pound (EGP)", "language": "Arabic",
        "warm_months": "1,2,3,4,5,10,11,12", "tags": "history,beach,desert,culture",
        "daily_spend": 40,
        "monuments": [
            ("Pyramids of Giza & the Sphinx", "Giza", 14, "The Great Pyramid of Khufu, 4,500 years old and still standing."),
            ("Grand Egyptian Museum", "Giza", 25, "The new home of Tutankhamun's treasures, next to the pyramids."),
            ("Karnak Temple", "Luxor", 12, "A forest of giant columns, the largest religious site of the ancient world."),
            ("Valley of the Kings", "Luxor", 16, "Painted royal tombs cut into the desert cliffs."),
            ("Abu Simbel", "Aswan", 20, "Four colossal statues of Ramses II carved into a mountain."),
        ],
        "restaurants": [
            ("Abou Tarek", "Cairo", "Koshari", "$", 3, "Four floors dedicated to one dish: Egypt's famous koshari."),
            ("Felfela", "Cairo", "Ful medames & ta'ameya", "$", 6, "A downtown institution for falafel and fava beans since 1959."),
            ("Naguib Mahfouz Cafe", "Cairo", "Mezze & mint tea", "$$", 15, "A calm, lantern-lit cafe inside the Khan el-Khalili bazaar."),
            ("Sofra", "Luxor", "Stuffed pigeon & molokhia", "$$", 12, "Traditional Egyptian dishes in an old house with a rooftop."),
        ],
        "stays": [
            ("Marriott Mena House", "hotel", "Giza", 260, 4.6, "A historic palace hotel with the Great Pyramid in the garden view."),
            ("Steigenberger Hotel El Tahrir", "hotel", "Cairo", 110, 4.3, "Modern hotel steps from the Egyptian Museum."),
            ("Zamalek Nile View Flat", "apartment", "Cairo", 70, 4.5, "A bright flat on Zamalek island overlooking the Nile."),
            ("Luxor West Bank Guesthouse", "apartment", "Luxor", 45, 4.7, "Mud-brick guesthouse among fields, near the Valley of the Kings."),
        ],
        "flights": [
            ("EgyptAir", "MS716", "Cairo", "Direct", date(2026, 12, 20), date(2026, 12, 27), 310, 45),
            ("Middle East Airlines", "ME305", "Cairo", "Direct", date(2027, 3, 8), date(2027, 3, 13), 290, 40),
            ("EgyptAir", "MS716", "Cairo", "Direct", date(2027, 3, 20), date(2027, 3, 25), 275, 45),
            ("EgyptAir", "MS718", "Luxor", "via Cairo", date(2027, 2, 12), date(2027, 2, 19), 360, 30),
        ],
    },
    {
        "name": "Thailand", "slug": "thailand",
        "tagline": "Golden temples, street food, island hopping.",
        "description": "Glittering temples in Bangkok, misty mountains around Chiang Mai and "
                       "turquoise islands in the south, plus street food that is cheap, fast and "
                       "unforgettable.",
        "best_time": "November to April",
        "currency": "Thai Baht (THB)", "language": "Thai",
        "warm_months": "1,2,3,4,5,11,12", "tags": "beach,food,culture,nature",
        "daily_spend": 45,
        "monuments": [
            ("The Grand Palace & Wat Phra Kaew", "Bangkok", 16, "The royal palace and the revered Emerald Buddha."),
            ("Wat Arun", "Bangkok", 3, "The Temple of Dawn, covered in coloured porcelain, by the river."),
            ("Wat Pho", "Bangkok", 9, "Home of a 46-metre golden reclining Buddha and Thai massage school."),
            ("Ayutthaya Historical Park", "Ayutthaya", 2, "Ruins of the old Siamese capital, best seen by bicycle."),
            ("Wat Phra That Doi Suthep", "Chiang Mai", 1, "A golden mountain temple above Chiang Mai."),
        ],
        "restaurants": [
            ("Thip Samai", "Bangkok", "Pad thai wrapped in egg", "$", 5, "Bangkok's most famous pad thai, cooked over charcoal since 1966."),
            ("Raan Jay Fai", "Bangkok", "Crab omelette", "$$$", 45, "A street-food chef in ski goggles who earned a Michelin star."),
            ("Khao Soi Khun Yai", "Chiang Mai", "Khao soi curry noodles", "$", 2, "A tiny lunch spot serving northern Thailand's signature dish."),
            ("Yaowarat Road Night Market", "Bangkok", "Street seafood & mango sticky rice", "$", 8, "Chinatown after dark: hundreds of street-food carts."),
        ],
        "stays": [
            ("Mandarin Oriental Bangkok", "hotel", "Bangkok", 520, 4.9, "A legendary riverside hotel, open since 1876."),
            ("Riva Surya Bangkok", "hotel", "Bangkok", 120, 4.5, "Calm boutique hotel on the river near Khao San Road."),
            ("Old City Teak House", "apartment", "Chiang Mai", 55, 4.8, "A wooden Lanna-style house inside the old city walls."),
            ("Sukhumvit Skyline Condo", "apartment", "Bangkok", 65, 4.4, "High-floor condo with an infinity pool, near the BTS skytrain."),
        ],
        "flights": [
            ("Emirates", "EK372", "Bangkok", "via Dubai", date(2027, 1, 15), date(2027, 1, 26), 820, 30),
            ("Qatar Airways", "QR830", "Bangkok", "via Doha", date(2027, 3, 10), date(2027, 3, 15), 760, 30),
            ("Etihad Airways", "EY406", "Bangkok", "via Abu Dhabi", date(2027, 3, 22), date(2027, 3, 29), 790, 28),
            ("Qatar Airways", "QR836", "Phuket", "via Doha", date(2027, 11, 12), date(2027, 11, 22), 880, 26),
        ],
    },
]

# ---------------------------------------------------------------------------
# Guides: (full name, email, country slug, languages, $ per day, status, bio)
# The first one is the test guide account.
# ---------------------------------------------------------------------------
GUIDES = [
    ("Marco Rossi", TEST_ACCOUNTS["guide"][0], "italy", "English, Italian, Arabic", 120, "approved",
     "Roman born and raised. I studied archaeology and I'll show you the Colosseum's underground and the best supplì in Trastevere."),
    ("Giulia Bianchi", "giulia@rihla.test", "italy", "English, Italian, French", 140, "approved",
     "Florence-based art historian. Uffizi without the queues, then a wine bar only locals know."),
    ("Haruto Sato", "haruto@rihla.test", "japan", "English, Japanese", 160, "approved",
     "Tokyo foodie and former sushi apprentice. I plan routes around train passes and the best ramen."),
    ("Yuki Tanaka", "yuki@rihla.test", "japan", "Japanese, English, Spanish", 150, "pending",
     "Kyoto tea-ceremony teacher. Temples at sunrise before the crowds arrive."),
    ("Eleni Papadopoulou", "eleni@rihla.test", "greece", "English, Greek, Arabic", 110, "approved",
     "Licensed Acropolis guide. Myths, history and the best loukoumades in Athens."),
    ("Nikos Georgiou", "nikos@rihla.test", "greece", "English, Greek", 100, "approved",
     "Island hopper and sailor. Let's find the quiet beaches of Santorini and Naxos."),
    ("Elif Yilmaz", "elif@rihla.test", "turkey", "English, Turkish, Arabic", 90, "approved",
     "Istanbul from both continents: bazaars, ferries and a proper Turkish breakfast."),
    ("Mehmet Kaya", "mehmet@rihla.test", "turkey", "English, Turkish, German", 80, "approved",
     "Cappadocia hiking guide. Valleys, cave churches and sunrise balloon spots."),
    ("Omar Hassan", "omar@rihla.test", "egypt", "Arabic, English, French", 70, "approved",
     "Egyptologist from Giza. I read hieroglyphs and know exactly when the pyramids are empty."),
    ("Nour El-Sayed", "nour@rihla.test", "egypt", "Arabic, English", 75, "approved",
     "Luxor local. Temples by day, felucca on the Nile at sunset."),
    ("Somchai Wongsakul", "somchai@rihla.test", "thailand", "Thai, English", 65, "approved",
     "Bangkok street-food expert. Twelve dishes, four markets, one tuk-tuk."),
    ("Ploy Chaiyaporn", "ploy@rihla.test", "thailand", "Thai, English, Chinese", 70, "pending",
     "Chiang Mai nature guide: elephant sanctuaries, waterfalls and hill-tribe villages."),
]

# Extra fictional travelers who already completed trips and left reviews.
EXTRA_TRAVELERS = [
    ("Lara Haddad", "lara@rihla.test"),
    ("Karim Nassar", "karim@rihla.test"),
]
EXTRA_PASSWORD = "Traveler123!"


def _add_user(full_name, email, password, role):
    user = User(full_name=full_name, email=email, role=role)
    user.set_password(password)  # stores only the hash
    db.session.add(user)
    return user


def _review(booking, guide, traveler, rating, comment):
    """Attach a review to the guide line of a (past) booking."""
    item = next(i for i in booking.items if i.guide_id == guide.id)
    db.session.add(Review(booking_item=item, guide=guide, traveler=traveler,
                          rating=rating, comment=comment))


def seed_database():
    """Fill an EMPTY database with all the sample data above."""
    # 1. Settings
    Setting.set("commission_rate", "10")

    # 2. Countries and their monuments, restaurants, stays and flights
    countries = {}
    for c in COUNTRIES:
        country = Country(
            name=c["name"], slug=c["slug"], tagline=c["tagline"], description=c["description"],
            best_time=c["best_time"], currency=c["currency"], language=c["language"],
            warm_months=c["warm_months"], tags=c["tags"],
            avg_daily_spend_cents=usd(c["daily_spend"]),
        )
        for name, city, cost, desc in c["monuments"]:
            country.monuments.append(Monument(name=name, city=city, entry_cost_cents=usd(cost), description=desc))
        for name, city, dish, price_range, meal, desc in c["restaurants"]:
            country.restaurants.append(Restaurant(name=name, city=city, must_try_dish=dish, price_range=price_range,
                                                  avg_meal_cost_cents=usd(meal), description=desc))
        for name, stay_type, city, night, rating, desc in c["stays"]:
            country.stays.append(Stay(name=name, type=stay_type, city=city, price_per_night_cents=usd(night),
                                      rating=rating, description=desc))
        for airline, number, to_city, stops, depart, ret, price, seats in c["flights"]:
            country.flights.append(Flight(airline=airline, flight_number=number, from_city="Beirut",
                                          to_city=to_city, stops=stops, depart_date=depart, return_date=ret,
                                          price_cents=usd(price), seats_total=seats, seats_available=seats))
        db.session.add(country)
        countries[c["slug"]] = country

    # 3. Users: admin, test traveler, extra travelers, guides
    _add_user("Rihla Admin", *TEST_ACCOUNTS["admin"], role="admin")
    maya = _add_user("Maya Khoury", *TEST_ACCOUNTS["traveler"], role="traveler")
    lara, karim = (_add_user(name, email, EXTRA_PASSWORD, "traveler") for name, email in EXTRA_TRAVELERS)

    guides = {}
    for full_name, email, slug, languages, price, status, bio in GUIDES:
        password = TEST_ACCOUNTS["guide"][1]
        user = _add_user(full_name, email, password, "guide")
        profile = GuideProfile(user=user, country=countries[slug], languages=languages, bio=bio,
                               price_per_day_cents=usd(price), status=status)
        db.session.add(profile)
        guides[email.split("@")[0]] = profile  # "guide", "giulia", "haruto"...

    db.session.commit()  # save everything so bookings can find it by id

    # 4. Bookings, made with the REAL booking service (same code as checkout).
    marco, eleni, elif_, mehmet, omar = (guides[k] for k in ("guide", "eleni", "elif", "mehmet", "omar"))
    stay = {s.name: s for s in Stay.query.all()}
    flight = {(f.flight_number, f.depart_date): f for f in Flight.query.all()}

    # Past trips (already happened) -> they can be reviewed
    b1 = create_booking(lara, [
        {"type": "stay", "id": stay["Hotel Santa Maria"].id, "quantity": 4},
        {"type": "guide", "id": marco.id, "quantity": 2},
    ], date(2026, 9, 10), date(2026, 9, 14), allow_past=True)
    _review(b1, marco, lara, 5, "Marco took us under the Colosseum and to a tiny trattoria we'd never have found. Perfect!")

    b2 = create_booking(karim, [
        {"type": "stay", "id": stay["Trastevere Rooftop Loft"].id, "quantity": 3},
        {"type": "guide", "id": marco.id, "quantity": 1},
    ], date(2026, 10, 2), date(2026, 10, 5), allow_past=True)
    _review(b2, marco, karim, 4, "Very knowledgeable, a bit fast-paced but we saw everything.")

    b3 = create_booking(karim, [
        {"type": "stay", "id": stay["Herodion Hotel"].id, "quantity": 3},
        {"type": "guide", "id": eleni.id, "quantity": 1},
    ], date(2026, 6, 12), date(2026, 6, 15), allow_past=True)
    _review(b3, eleni, karim, 5, "Eleni made the Acropolis come alive. Book her early!")

    b4 = create_booking(lara, [
        {"type": "stay", "id": stay["Sirkeci Mansion"].id, "quantity": 4},
        {"type": "guide", "id": elif_.id, "quantity": 2},
    ], date(2026, 5, 3), date(2026, 5, 7), allow_past=True)
    _review(b4, elif_, lara, 4, "Great food tour on the Asian side. The ferry ride was a highlight.")

    # The test traveler's past trip: NOT reviewed yet, so you can demo the review form.
    create_booking(maya, [
        {"type": "stay", "id": stay["Cappadocia Cave Suite"].id, "quantity": 3},
        {"type": "guide", "id": mehmet.id, "quantity": 2},
    ], date(2026, 10, 20), date(2026, 10, 23), allow_past=True)

    # The test traveler's upcoming trip: includes a flight, so seats go down by 2.
    tokyo = flight[("EK958", date(2027, 4, 10))]
    create_booking(maya, [
        {"type": "flight", "id": tokyo.id, "quantity": 2},
        {"type": "stay", "id": stay["Kyoto Machiya Townhouse"].id, "quantity": 10},
    ], tokyo.depart_date, tokyo.return_date)

    # An upcoming trip by another traveler (so the guide and admin dashboards have data).
    cairo = flight[("ME305", date(2027, 3, 8))]
    create_booking(karim, [
        {"type": "flight", "id": cairo.id, "quantity": 1},
        {"type": "stay", "id": stay["Marriott Mena House"].id, "quantity": 5},
        {"type": "guide", "id": omar.id, "quantity": 2},
    ], cairo.depart_date, cairo.return_date)

    db.session.commit()  # saves the reviews
