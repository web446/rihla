-- Rihla database schema (SQLite)
-- GENERATED from models.py by db.create_all(). Do not edit by hand:
-- change models.py, run "flask --app app init-db", then export again.

CREATE TABLE users (
	id INTEGER NOT NULL, 
	full_name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_user_role CHECK (role IN ('traveler', 'guide', 'admin'))
);

CREATE TABLE countries (
	id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	slug VARCHAR(80) NOT NULL, 
	tagline VARCHAR(150), 
	description TEXT NOT NULL, 
	best_time VARCHAR(100) NOT NULL, 
	currency VARCHAR(50) NOT NULL, 
	language VARCHAR(50) NOT NULL, 
	warm_months VARCHAR(40) NOT NULL, 
	tags VARCHAR(150) NOT NULL, 
	avg_daily_spend_cents INTEGER NOT NULL, 
	hero_image VARCHAR(500), 
	hero_credit VARCHAR(300), 
	hero_source VARCHAR(500), 
	entry_type VARCHAR(20) NOT NULL, 
	max_stay VARCHAR(60) NOT NULL, 
	entry_notes TEXT NOT NULL, 
	popularity INTEGER NOT NULL, 
	popularity_note VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_country_entry CHECK (entry_type IN ('visa_free', 'visa_on_arrival', 'conditional', 'evisa')), 
	CONSTRAINT ck_country_popularity CHECK (popularity BETWEEN 1 AND 5), 
	UNIQUE (name), 
	UNIQUE (slug)
);

CREATE TABLE settings (
	"key" VARCHAR(50) NOT NULL, 
	value VARCHAR(200) NOT NULL, 
	PRIMARY KEY ("key")
);

CREATE TABLE guide_profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	country_id INTEGER NOT NULL, 
	languages VARCHAR(150) NOT NULL, 
	bio TEXT NOT NULL, 
	price_per_day_cents INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	photo VARCHAR(255), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_guide_status CHECK (status IN ('pending', 'approved', 'rejected')), 
	CONSTRAINT ck_guide_price CHECK (price_per_day_cents > 0), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(country_id) REFERENCES countries (id)
);

CREATE TABLE monuments (
	id INTEGER NOT NULL, 
	country_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	city VARCHAR(80) NOT NULL, 
	description TEXT NOT NULL, 
	entry_cost_cents INTEGER NOT NULL, 
	image VARCHAR(500), 
	image_credit VARCHAR(300), 
	image_source VARCHAR(500), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_monument_cost CHECK (entry_cost_cents >= 0), 
	FOREIGN KEY(country_id) REFERENCES countries (id)
);

CREATE TABLE restaurants (
	id INTEGER NOT NULL, 
	country_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	city VARCHAR(80) NOT NULL, 
	must_try_dish VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	price_range VARCHAR(3) NOT NULL, 
	avg_meal_cost_cents INTEGER NOT NULL, 
	image VARCHAR(255), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_restaurant_price CHECK (price_range IN ('$', '$$', '$$$')), 
	FOREIGN KEY(country_id) REFERENCES countries (id)
);

CREATE TABLE stays (
	id INTEGER NOT NULL, 
	country_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	type VARCHAR(10) NOT NULL, 
	city VARCHAR(80) NOT NULL, 
	description TEXT NOT NULL, 
	price_per_night_cents INTEGER NOT NULL, 
	rating FLOAT NOT NULL, 
	image VARCHAR(255), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_stay_type CHECK (type IN ('hotel', 'apartment')), 
	CONSTRAINT ck_stay_price CHECK (price_per_night_cents > 0), 
	FOREIGN KEY(country_id) REFERENCES countries (id)
);

CREATE TABLE flights (
	id INTEGER NOT NULL, 
	country_id INTEGER NOT NULL, 
	airline VARCHAR(60) NOT NULL, 
	flight_number VARCHAR(12) NOT NULL, 
	from_city VARCHAR(60) NOT NULL, 
	to_city VARCHAR(60) NOT NULL, 
	stops VARCHAR(60) NOT NULL, 
	depart_date DATE NOT NULL, 
	return_date DATE NOT NULL, 
	price_cents INTEGER NOT NULL, 
	seats_total INTEGER NOT NULL, 
	seats_available INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_flight_seats CHECK (seats_available >= 0 AND seats_available <= seats_total), 
	CONSTRAINT ck_flight_dates CHECK (return_date >= depart_date), 
	FOREIGN KEY(country_id) REFERENCES countries (id)
);

CREATE TABLE bookings (
	id INTEGER NOT NULL, 
	traveler_id INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	total_cents INTEGER NOT NULL, 
	commission_rate FLOAT NOT NULL, 
	commission_cents INTEGER NOT NULL, 
	provider_cents INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	source VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_booking_status CHECK (status IN ('confirmed', 'cancelled')), 
	CONSTRAINT ck_booking_source CHECK (source IN ('web', 'agent')), 
	FOREIGN KEY(traveler_id) REFERENCES users (id)
);

CREATE TABLE chat_conversations (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE booking_items (
	id INTEGER NOT NULL, 
	booking_id INTEGER NOT NULL, 
	item_type VARCHAR(10) NOT NULL, 
	flight_id INTEGER, 
	stay_id INTEGER, 
	guide_id INTEGER, 
	quantity INTEGER NOT NULL, 
	unit_price_cents INTEGER NOT NULL, 
	line_total_cents INTEGER NOT NULL, 
	commission_cents INTEGER NOT NULL, 
	provider_cents INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_item_type CHECK (item_type IN ('flight', 'stay', 'guide')), 
	CONSTRAINT ck_item_quantity CHECK (quantity > 0), 
	CONSTRAINT ck_item_one_target CHECK ((CASE WHEN flight_id IS NOT NULL THEN 1 ELSE 0 END) + (CASE WHEN stay_id IS NOT NULL THEN 1 ELSE 0 END) + (CASE WHEN guide_id IS NOT NULL THEN 1 ELSE 0 END) = 1), 
	FOREIGN KEY(booking_id) REFERENCES bookings (id), 
	FOREIGN KEY(flight_id) REFERENCES flights (id), 
	FOREIGN KEY(stay_id) REFERENCES stays (id), 
	FOREIGN KEY(guide_id) REFERENCES guide_profiles (id)
);

CREATE TABLE chat_messages (
	id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	cards_json TEXT, 
	api_json TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_msg_role CHECK (role IN ('user', 'assistant', 'tool')), 
	FOREIGN KEY(conversation_id) REFERENCES chat_conversations (id)
);

CREATE TABLE booking_proposals (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	conversation_id INTEGER, 
	action VARCHAR(10) NOT NULL, 
	payload_json TEXT NOT NULL, 
	total_cents INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_proposal_action CHECK (action IN ('create', 'cancel')), 
	CONSTRAINT ck_proposal_status CHECK (status IN ('pending', 'confirmed', 'expired')), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(conversation_id) REFERENCES chat_conversations (id)
);

CREATE TABLE reviews (
	id INTEGER NOT NULL, 
	booking_item_id INTEGER NOT NULL, 
	guide_id INTEGER NOT NULL, 
	traveler_id INTEGER NOT NULL, 
	rating INTEGER NOT NULL, 
	comment TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5), 
	UNIQUE (booking_item_id), 
	FOREIGN KEY(booking_item_id) REFERENCES booking_items (id), 
	FOREIGN KEY(guide_id) REFERENCES guide_profiles (id), 
	FOREIGN KEY(traveler_id) REFERENCES users (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_chat_messages_created_at ON chat_messages (created_at);

