"""Sample data so the site looks full during the demo.

Run with:   flask --app app init-db
It DELETES all tables, creates them again, and inserts everything below.

The 6 destinations are countries an ordinary LEBANESE passport holder can
enter without applying for a visa in advance (researched November 2026, see
docs/VISA_RESEARCH.md). Egypt is visa-free only under conditions, shown on
the site. Visa rules change: always check official sources before travelling.

Prices are realistic estimates in US dollars, written here in dollars and
turned into cents by usd(). Flights, hotel prices and bookings are SIMULATED.
Monuments, restaurants and most hotels are real places; the people (guides,
travelers) and the apartments are fictional.
"""
from datetime import date

from extensions import db
from models import (Country, Flight, GuideProfile, Monument, Restaurant, Review,
                    Setting, Stay, User)
from photos import PHOTOS   # real photos from Wikimedia Commons, with author + licence
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
# entry_type: visa_free | visa_on_arrival | conditional | evisa  (for a Lebanese passport)
# popularity: 1-5 stars with Lebanese travelers
# Each monument: (name, city, entry cost $, description)
# Each restaurant: (name, city, must-try dish, price range, avg meal $, description)
# Each stay: (name, type, city, $ per night, rating, description)
# Each flight: (airline, number, to_city, stops, depart, return, $ per seat, seats)
#   stops starting with "Direct" = non-stop from Beirut
# ---------------------------------------------------------------------------
COUNTRIES = [
    {
        "name": "Turkey", "slug": "turkey",
        "tagline": "Two continents, one breakfast table.",
        "description": "Istanbul straddles Europe and Asia, Cappadocia floats in hot-air balloons "
                       "and the Turquoise Coast is a short hop from Beirut. Close, affordable and "
                       "the favourite getaway of Lebanese travelers.",
        "best_time": "April to May, September to November",
        "currency": "Turkish Lira (TRY)", "language": "Turkish",
        "warm_months": "5,6,7,8,9,10", "tags": "history,food,city,beach,culture",
        "daily_spend": 55,
        "entry_type": "visa_free", "max_stay": "90 days in any 180",
        "entry_notes": "No visa needed. Stays cannot be extended: for longer stays you need a residence permit.",
        "popularity": 5,
        "popularity_note": "#1 destination: about 245,000 Lebanese visitors in 2025, and Beirut-Istanbul is the airport's busiest route.",
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
            ("Pegasus Airlines", "PC749", "Antalya", "Direct", date(2027, 6, 10), date(2027, 6, 17), 280, 40),
            ("Turkish Airlines", "TK829", "Istanbul", "Direct", date(2027, 9, 9), date(2027, 9, 16), 300, 45),
        ],
    },
    {
        "name": "Armenia", "slug": "armenia",
        "tagline": "Ancient monasteries, apricots and mountain air.",
        "description": "Pink-stone Yerevan, a pagan temple above a canyon, monasteries carved into "
                       "cliffs and Lake Sevan in the mountains. Two hours from Beirut, and home to "
                       "close family ties with Lebanon's Armenian community.",
        "best_time": "May to June, September to October",
        "currency": "Armenian Dram (AMD)", "language": "Armenian",
        "warm_months": "6,7,8,9", "tags": "history,culture,nature,food",
        "daily_spend": 50,
        "entry_type": "visa_on_arrival", "max_stay": "120 days per year",
        "entry_notes": "Get the visa on arrival at Yerevan airport, or apply for an e-Visa online before you go.",
        "popularity": 4,
        "popularity_note": "In almost every Lebanese travel agency's packages; strong Lebanese-Armenian community.",
        "monuments": [
            ("Garni Temple", "Garni", 4, "A 1st-century Greco-Roman temple on the edge of a basalt canyon."),
            ("Geghard Monastery", "Goght", 0, "A UNESCO monastery partly carved out of the mountain rock."),
            ("Wings of Tatev", "Tatev", 13, "The world's longest reversible cable car, flying to Tatev Monastery."),
            ("Cascade Complex", "Yerevan", 0, "Giant stairs with modern art and the best view of Mount Ararat."),
            ("Khor Virap", "Ararat", 0, "A monastery facing Mount Ararat, where Armenia became Christian."),
        ],
        "restaurants": [
            ("Lavash Restaurant", "Yerevan", "Khorovats (Armenian barbecue)", "$$", 20, "Lavash bread baked in front of you and grilled meats."),
            ("Tavern Yerevan", "Yerevan", "Dolma in vine leaves", "$$", 15, "Classic Armenian dishes with live folk music."),
            ("Dolmama", "Yerevan", "Modern dolma", "$$$", 35, "A creative take on Armenian cuisine in a 19th-century house."),
            ("Sherep", "Yerevan", "Ghapama (stuffed pumpkin)", "$$", 22, "Open kitchen near Republic Square."),
        ],
        "stays": [
            ("Tufenkian Historic Yerevan Hotel", "hotel", "Yerevan", 140, 4.6, "Boutique hotel with handmade Armenian carpets."),
            ("Paris Hotel Yerevan", "hotel", "Yerevan", 110, 4.5, "Rooftop restaurant facing Mount Ararat."),
            ("Cascade View Apartment", "apartment", "Yerevan", 65, 4.7, "Bright flat a short walk from the Cascade."),
            ("Dilijan Forest Cabin", "apartment", "Dilijan", 55, 4.8, "A wooden cabin in Armenia's 'little Switzerland'."),
        ],
        "flights": [
            ("Middle East Airlines", "ME311", "Yerevan", "Direct", date(2026, 12, 17), date(2026, 12, 24), 350, 36),
            ("Middle East Airlines", "ME311", "Yerevan", "Direct", date(2027, 4, 16), date(2027, 4, 23), 330, 36),
            ("Middle East Airlines", "ME311", "Yerevan", "Direct", date(2027, 6, 11), date(2027, 6, 18), 380, 36),
            ("Middle East Airlines", "ME311", "Yerevan", "Direct", date(2027, 9, 10), date(2027, 9, 17), 360, 36),
        ],
    },
    {
        "name": "Egypt", "slug": "egypt",
        "tagline": "Five thousand years, still warm.",
        "description": "Stand in front of the last surviving Wonder of the Ancient World, sail the "
                       "Nile past Luxor's temples and snorkel the Red Sea from Sharm El Sheikh. "
                       "Warm almost all year and one of the best-value trips from Beirut.",
        "best_time": "October to April",
        "currency": "Egyptian Pound (EGP)", "language": "Arabic",
        "warm_months": "1,2,3,4,5,10,11,12", "tags": "history,beach,desert,culture",
        "daily_spend": 40,
        "entry_type": "conditional", "max_stay": "90 days in any 180",
        "entry_notes": "Visa-free ONLY if you arrive on a charter flight at Sharm El Sheikh, Hurghada or Borg El "
                       "Arab, travel in a tour group of 10 or more, or are under 16 or over 50. Otherwise get a "
                       "visa before travelling. Rihla's charter flights to Sharm El Sheikh and Hurghada qualify.",
        "popularity": 4,
        "popularity_note": "A classic for Lebanese families and Red Sea holidays (estimate).",
        "monuments": [
            ("Pyramids of Giza & the Sphinx", "Giza", 14, "The Great Pyramid of Khufu, 4,500 years old and still standing."),
            ("Grand Egyptian Museum", "Giza", 25, "The new home of Tutankhamun's treasures, next to the pyramids."),
            ("Karnak Temple", "Luxor", 12, "A forest of giant columns, the largest religious site of the ancient world."),
            ("Ras Mohammed National Park", "Sharm El Sheikh", 5, "Coral reefs, angelfish and some of the best snorkelling in the Red Sea."),
            ("Valley of the Kings", "Luxor", 16, "Painted royal tombs cut into the desert cliffs."),
        ],
        "restaurants": [
            ("Abou Tarek", "Cairo", "Koshari", "$", 3, "Four floors dedicated to one dish: Egypt's famous koshari."),
            ("Felfela", "Cairo", "Ful medames & ta'ameya", "$", 6, "A downtown institution for falafel and fava beans since 1959."),
            ("Naguib Mahfouz Cafe", "Cairo", "Mezze & mint tea", "$$", 15, "A calm, lantern-lit cafe inside the Khan el-Khalili bazaar."),
            ("Fares Seafood", "Sharm El Sheikh", "Grilled Red Sea fish", "$$", 18, "Choose your fish by weight in Sharm's Old Market."),
        ],
        "stays": [
            ("Marriott Mena House", "hotel", "Giza", 260, 4.6, "A historic palace hotel with the Great Pyramid in the garden view."),
            ("Rixos Sharm El Sheikh", "hotel", "Sharm El Sheikh", 220, 4.7, "All-inclusive beach resort on Nabq Bay."),
            ("Zamalek Nile View Flat", "apartment", "Cairo", 70, 4.5, "A bright flat on Zamalek island overlooking the Nile."),
            ("Luxor West Bank Guesthouse", "apartment", "Luxor", 45, 4.7, "Mud-brick guesthouse among fields, near the Valley of the Kings."),
        ],
        "flights": [
            ("EgyptAir", "MS716", "Cairo", "Direct", date(2026, 12, 20), date(2026, 12, 27), 310, 45),
            ("Middle East Airlines", "ME305", "Cairo", "Direct", date(2027, 3, 8), date(2027, 3, 13), 290, 40),
            ("Middle East Airlines", "ME5501", "Sharm El Sheikh", "Direct (charter)", date(2027, 3, 20), date(2027, 3, 25), 310, 60),
            ("Middle East Airlines", "ME5503", "Hurghada", "Direct (charter)", date(2027, 4, 24), date(2027, 5, 1), 330, 60),
        ],
    },
    {
        "name": "Jordan", "slug": "jordan",
        "tagline": "Rose-red cities and a desert under the stars.",
        "description": "Walk the Siq to Petra's Treasury, sleep in a Bedouin camp in Wadi Rum, float "
                       "in the Dead Sea and wander Roman Jerash. One hour from Beirut, and no visa "
                       "for Lebanese travelers.",
        "best_time": "March to May, September to November",
        "currency": "Jordanian Dinar (JOD)", "language": "Arabic",
        "warm_months": "4,5,6,7,8,9,10", "tags": "history,desert,nature,food",
        "daily_spend": 60,
        "entry_type": "visa_free", "max_stay": "3 months in any 6",
        "entry_notes": "No visa needed. Iris scan on entry and exit. Not valid with emergency or temporary passports.",
        "popularity": 3,
        "popularity_note": "Short, easy trip with daily direct flights (estimate).",
        "monuments": [
            ("Petra", "Wadi Musa", 71, "The rose-red Nabataean city carved into the cliffs: the Treasury, then 800 steps up to the Monastery."),
            ("Wadi Rum Protected Area", "Wadi Rum", 7, "Red sand dunes and rock arches where 'The Martian' was filmed."),
            ("Jerash", "Jerash", 14, "One of the best-preserved Roman cities outside Italy."),
            ("Amman Citadel", "Amman", 4, "The Temple of Hercules above the capital's seven hills."),
            ("Dead Sea (Amman Beach)", "Dead Sea", 28, "Float effortlessly at the lowest point on Earth."),
        ],
        "restaurants": [
            ("Hashem Restaurant", "Amman", "Falafel & hummus", "$", 5, "Open almost around the clock since 1952 in downtown Amman."),
            ("Sufra", "Amman", "Mansaf", "$$", 20, "Jordan's national dish in a villa on Rainbow Street."),
            ("Habibah Sweets", "Amman", "Knafeh", "$", 3, "Queue in the alley for hot, cheesy knafeh."),
            ("Petra Kitchen", "Wadi Musa", "Cook-your-own Jordanian dinner", "$$$", 45, "A cooking class next to Petra, then dinner."),
        ],
        "stays": [
            ("The House Boutique Suites", "hotel", "Amman", 110, 4.6, "Spacious suites in quiet Shmeisani."),
            ("Movenpick Resort Petra", "hotel", "Wadi Musa", 190, 4.6, "Right at the entrance of Petra."),
            ("Wadi Rum Desert Camp", "apartment", "Wadi Rum", 90, 4.7, "A Bedouin-style tent with dinner under the stars."),
            ("Jabal Amman Loft", "apartment", "Amman", 60, 4.5, "A flat with a terrace near Rainbow Street."),
        ],
        "flights": [
            ("Royal Jordanian", "RJ401", "Amman", "Direct", date(2026, 12, 11), date(2026, 12, 15), 230, 40),
            ("Middle East Airlines", "ME312", "Amman", "Direct", date(2027, 3, 26), date(2027, 3, 30), 220, 40),
            ("Royal Jordanian", "RJ403", "Amman", "Direct", date(2027, 4, 23), date(2027, 4, 28), 240, 40),
            ("Middle East Airlines", "ME312", "Amman", "Direct", date(2027, 10, 15), date(2027, 10, 20), 250, 40),
        ],
    },
    {
        "name": "Georgia", "slug": "georgia",
        "tagline": "Wine, mountains and the warmest welcome.",
        "description": "Cobbled Old Tbilisi with its balconies and sulphur baths, the Gergeti church "
                       "under Mount Kazbek and 8,000 years of wine in Kakheti. Lebanese travelers "
                       "can stay up to a whole year without a visa.",
        "best_time": "May to June, September to October",
        "currency": "Georgian Lari (GEL)", "language": "Georgian",
        "warm_months": "6,7,8,9", "tags": "nature,food,city,culture",
        "daily_spend": 50,
        "entry_type": "visa_free", "max_stay": "1 year",
        "entry_notes": "No visa needed. Travel health insurance covering your whole stay is mandatory "
                       "(at least 30,000 GEL of medical cover).",
        "popularity": 3,
        "popularity_note": "Growing fast thanks to the 1-year visa-free stay (estimate).",
        "monuments": [
            ("Narikala Fortress", "Tbilisi", 0, "A 4th-century fortress above the Old Town, reached by cable car."),
            ("Gergeti Trinity Church", "Kazbegi", 0, "A 14th-century church alone under 5,000-metre Mount Kazbek."),
            ("Jvari Monastery", "Mtskheta", 0, "A 6th-century monastery where two rivers meet."),
            ("Uplistsikhe Cave Town", "Gori", 6, "A 3,000-year-old town carved into the rock."),
            ("Sighnaghi Town Walls", "Sighnaghi", 0, "Walk the walls of the 'city of love' above the vineyards."),
        ],
        "restaurants": [
            ("Pasanauri", "Tbilisi", "Khinkali dumplings", "$", 8, "The place to learn how to eat khinkali by hand."),
            ("Shavi Lomi", "Tbilisi", "Modern Georgian dishes", "$$", 20, "Creative Georgian cooking in a garden courtyard."),
            ("Cafe Littera", "Tbilisi", "Adjarian khachapuri", "$$$", 40, "Garden restaurant in the Writers' House."),
            ("Pheasant's Tears", "Sighnaghi", "Qvevri wine & supra feast", "$$", 30, "Natural wine made in clay jars and a Georgian feast."),
        ],
        "stays": [
            ("Rooms Hotel Tbilisi", "hotel", "Tbilisi", 170, 4.7, "A former publishing house turned design hotel."),
            ("Rooms Hotel Kazbegi", "hotel", "Kazbegi", 160, 4.8, "Floor-to-ceiling views of Mount Kazbek."),
            ("Old Tbilisi Balcony Flat", "apartment", "Tbilisi", 55, 4.6, "A carved wooden balcony over the Old Town."),
            ("Sighnaghi Wine House", "apartment", "Sighnaghi", 50, 4.7, "A guesthouse with its own family wine cellar."),
        ],
        "flights": [
            ("Turkish Airlines", "TK823", "Tbilisi", "via Istanbul", date(2026, 12, 18), date(2026, 12, 26), 400, 30),
            ("Turkish Airlines", "TK823", "Tbilisi", "via Istanbul", date(2027, 5, 14), date(2027, 5, 21), 420, 30),
            ("Middle East Airlines", "ME341", "Tbilisi", "Direct (summer)", date(2027, 7, 9), date(2027, 7, 16), 460, 36),
            ("Middle East Airlines", "ME341", "Tbilisi", "Direct (summer)", date(2027, 9, 10), date(2027, 9, 17), 440, 36),
        ],
    },
    {
        "name": "Malaysia", "slug": "malaysia",
        "tagline": "Skyscrapers, rainforest and the best street food in Asia.",
        "description": "The Petronas Towers above Kuala Lumpur, the beaches of Langkawi, Penang's "
                       "hawker stalls and the rainforests of Borneo. Warm all year, and visa-free "
                       "for Lebanese travelers for up to 90 days.",
        "best_time": "March to October on the west coast",
        "currency": "Malaysian Ringgit (MYR)", "language": "Malay",
        "warm_months": "1,2,3,4,5,6,7,8,9,10,11,12", "tags": "beach,food,city,nature,islands",
        "daily_spend": 45,
        "entry_type": "visa_free", "max_stay": "90 days in any 180",
        "entry_notes": "No visa needed. Fingerprints are taken on entry and exit. Fill in the free Malaysia "
                       "Digital Arrival Card within 3 days before you arrive.",
        "popularity": 3,
        "popularity_note": "A favourite long-haul and honeymoon trip (estimate).",
        "monuments": [
            ("Petronas Twin Towers Skybridge", "Kuala Lumpur", 22, "Walk between the twin towers 170 metres up."),
            ("Batu Caves", "Gombak", 0, "272 rainbow steps up to a temple inside a limestone cave."),
            ("Langkawi SkyCab", "Langkawi", 19, "A steep cable car to the Sky Bridge above the rainforest."),
            ("Penang Hill Funicular", "George Town", 7, "Ride up for the view over Penang island."),
        ],
        "restaurants": [
            ("Jalan Alor Food Street", "Kuala Lumpur", "Satay & grilled stingray", "$", 8, "Kuala Lumpur's most famous night food street."),
            ("Village Park Restaurant", "Petaling Jaya", "Nasi lemak", "$", 5, "Often called the best nasi lemak in the country."),
            ("Penang Road Famous Teochew Chendul", "George Town", "Cendol", "$", 2, "Iced coconut dessert, served since 1936."),
            ("Bijan", "Kuala Lumpur", "Rendang & Malay classics", "$$", 30, "Elegant Malay cooking in a tropical garden."),
        ],
        "stays": [
            ("Mandarin Oriental Kuala Lumpur", "hotel", "Kuala Lumpur", 210, 4.7, "Next to the Petronas Towers and KLCC Park."),
            ("The Datai Langkawi", "hotel", "Langkawi", 650, 4.9, "A rainforest resort on a private bay."),
            ("Bukit Bintang Skyline Condo", "apartment", "Kuala Lumpur", 60, 4.5, "Rooftop infinity pool in the shopping district."),
            ("George Town Heritage Shophouse", "apartment", "George Town", 70, 4.8, "A restored shophouse in Penang's UNESCO old town."),
        ],
        "flights": [
            ("Emirates", "EK351", "Kuala Lumpur", "via Dubai", date(2026, 12, 19), date(2027, 1, 2), 920, 30),
            ("Qatar Airways", "QR844", "Kuala Lumpur", "via Doha", date(2027, 3, 12), date(2027, 3, 22), 870, 30),
            ("Turkish Airlines", "TK60", "Kuala Lumpur", "via Istanbul", date(2027, 4, 9), date(2027, 4, 19), 890, 30),
            ("Qatar Airways", "QR846", "Kuala Lumpur", "via Doha", date(2027, 7, 2), date(2027, 7, 14), 940, 30),
        ],
    },
]

# ---------------------------------------------------------------------------
# Guides: (full name, email, country slug, languages, $ per day, status, bio)
# The first one is the test guide account.
# ---------------------------------------------------------------------------
GUIDES = [
    ("Aram Petrosyan", TEST_ACCOUNTS["guide"][0], "armenia", "Armenian, English, Arabic", 120, "approved",
     "Born in Bourj Hammoud, living in Yerevan for 15 years. Monasteries, brandy cellars and the best khorovats in town."),
    ("Anahit Sargsyan", "anahit@rihla.test", "armenia", "Armenian, English, French", 100, "approved",
     "Historian and hiker. Day trips to Garni, Geghard and Lake Sevan at your pace."),
    ("Lina Haddadin", "lina@rihla.test", "jordan", "Arabic, English, French", 90, "approved",
     "Licensed Petra guide. I know the quiet trails to the Monastery, away from the crowds."),
    ("Khaled Al-Zalabieh", "khaled@rihla.test", "jordan", "Arabic, English", 80, "approved",
     "Bedouin from Wadi Rum. Jeep tours, sunset on the dunes and a night under the stars."),
    ("Giorgi Beridze", "giorgi@rihla.test", "georgia", "Georgian, English, Russian", 100, "approved",
     "Tbilisi foodie and mountain lover: khinkali in the city, then a road trip to Kazbegi."),
    ("Nino Kapanadze", "nino@rihla.test", "georgia", "Georgian, English, Arabic", 90, "pending",
     "Wine guide in Kakheti. I studied in Beirut and love showing Lebanese travelers our vineyards."),
    ("Elif Yilmaz", "elif@rihla.test", "turkey", "English, Turkish, Arabic", 90, "approved",
     "Istanbul from both continents: bazaars, ferries and a proper Turkish breakfast."),
    ("Mehmet Kaya", "mehmet@rihla.test", "turkey", "English, Turkish, German", 80, "approved",
     "Cappadocia hiking guide. Valleys, cave churches and sunrise balloon spots."),
    ("Omar Hassan", "omar@rihla.test", "egypt", "Arabic, English, French", 70, "approved",
     "Egyptologist from Giza. I read hieroglyphs and know exactly when the pyramids are empty."),
    ("Nour El-Sayed", "nour@rihla.test", "egypt", "Arabic, English", 75, "approved",
     "Sharm El Sheikh diving instructor and Luxor local: reefs by day, temples by night."),
    ("Aisyah Rahman", "aisyah@rihla.test", "malaysia", "Malay, English, Arabic", 70, "approved",
     "Kuala Lumpur food guide. Twelve dishes, three night markets, one very full stomach."),
    ("Daniel Tan", "daniel@rihla.test", "malaysia", "English, Malay, Chinese", 65, "pending",
     "Penang and Langkawi island-hopping, with the best hawker stalls on the way."),
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
            entry_type=c["entry_type"], max_stay=c["max_stay"], entry_notes=c["entry_notes"],
            popularity=c["popularity"], popularity_note=c["popularity_note"],
        )
        photo = PHOTOS.get(f"country:{c['slug']}")
        if photo:
            country.hero_image, country.hero_credit, country.hero_source = photo["url"], photo["credit"], photo["source"]
        for name, city, cost, desc in c["monuments"]:
            monument = Monument(name=name, city=city, entry_cost_cents=usd(cost), description=desc)
            photo = PHOTOS.get(f"monument:{name}")
            if photo:
                monument.image, monument.image_credit, monument.image_source = photo["url"], photo["credit"], photo["source"]
            country.monuments.append(monument)
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
        user = _add_user(full_name, email, TEST_ACCOUNTS["guide"][1], "guide")
        profile = GuideProfile(user=user, country=countries[slug], languages=languages, bio=bio,
                               price_per_day_cents=usd(price), status=status)
        db.session.add(profile)
        guides[email.split("@")[0]] = profile  # "guide", "anahit", "lina"...

    db.session.commit()  # save everything so bookings can find it by id

    # 4. Bookings, made with the REAL booking service (same code as checkout).
    aram, lina, elif_, mehmet, omar = (guides[k] for k in ("guide", "lina", "elif", "mehmet", "omar"))
    stay = {s.name: s for s in Stay.query.all()}
    flight = {(f.flight_number, f.depart_date): f for f in Flight.query.all()}

    # Past trips (already happened) -> they can be reviewed
    b1 = create_booking(lara, [
        {"type": "stay", "id": stay["Paris Hotel Yerevan"].id, "quantity": 4},
        {"type": "guide", "id": aram.id, "quantity": 2},
    ], date(2026, 9, 10), date(2026, 9, 14), allow_past=True)
    _review(b1, aram, lara, 5, "Aram took us to Geghard at sunrise and to a brandy cellar we'd never have found. Perfect!")

    b2 = create_booking(karim, [
        {"type": "stay", "id": stay["Cascade View Apartment"].id, "quantity": 3},
        {"type": "guide", "id": aram.id, "quantity": 1},
    ], date(2026, 10, 2), date(2026, 10, 5), allow_past=True)
    _review(b2, aram, karim, 4, "Very knowledgeable, a bit fast-paced but we saw everything.")

    b3 = create_booking(karim, [
        {"type": "stay", "id": stay["Movenpick Resort Petra"].id, "quantity": 3},
        {"type": "guide", "id": lina.id, "quantity": 1},
    ], date(2026, 6, 12), date(2026, 6, 15), allow_past=True)
    _review(b3, lina, karim, 5, "Lina made Petra come alive. Take her trail to the Monastery!")

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
    kl = flight[("TK60", date(2027, 4, 9))]
    create_booking(maya, [
        {"type": "flight", "id": kl.id, "quantity": 2},
        {"type": "stay", "id": stay["George Town Heritage Shophouse"].id, "quantity": 10},
    ], kl.depart_date, kl.return_date)

    # An upcoming trip by another traveler (so the guide and admin dashboards have data).
    sharm = flight[("ME5501", date(2027, 3, 20))]
    create_booking(karim, [
        {"type": "flight", "id": sharm.id, "quantity": 1},
        {"type": "stay", "id": stay["Rixos Sharm El Sheikh"].id, "quantity": 5},
        {"type": "guide", "id": guides["nour"].id, "quantity": 2},
    ], sharm.depart_date, sharm.return_date)

    db.session.commit()  # saves the reviews
