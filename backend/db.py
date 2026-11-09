"""Database foundation (task P1).

One SQLite file. Every table that holds user data has a user_id column, so a query can
always be limited to the logged-in user and one account never sees another account's data.
The other backend modules (recipes, shopping, plan, health, profile) already have their
tables here, so each owner can start without changing the schema.
"""
import json
import sqlite3
from contextlib import closing
from datetime import date, timedelta

from flask import current_app, g

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    recovery_hash TEXT,
    picture       TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Pantry (P3)
CREATE TABLE IF NOT EXISTS pantry_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    cat        TEXT NOT NULL DEFAULT 'Other',
    qty        REAL NOT NULL,
    unit       TEXT NOT NULL DEFAULT 'pcs',
    exp        TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pantry_user ON pantry_items(user_id);

CREATE TABLE IF NOT EXISTS pantry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'Other',
    quantity    REAL NOT NULL DEFAULT 1,
    unit        TEXT NOT NULL DEFAULT 'pcs',
    expiry_date TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pantry_merge_key ON pantry(user_id, lower(name), unit);

-- Diets, allergies, onboarding flag (P4)
CREATE TABLE IF NOT EXISTS dietary (
    user_id              INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    diets                TEXT NOT NULL DEFAULT '[]',
    allergies            TEXT NOT NULL DEFAULT '[]',
    onboarding_completed INTEGER NOT NULL DEFAULT 0
);

-- Notification preferences (P6)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    prefs   TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS settings (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferences     TEXT NOT NULL DEFAULT '{}',
    profile_picture TEXT
);

-- Recipes, favourites, ratings, shopping list (owner: S. Y. S. Jayathilaka)
CREATE TABLE IF NOT EXISTS recipes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    ingredients  TEXT NOT NULL DEFAULT '[]',
    instructions TEXT NOT NULL DEFAULT '',
    image        TEXT,
    diets        TEXT NOT NULL DEFAULT '[]',
    time_min     INTEGER,
    kcal         INTEGER,
    protein      REAL,
    carbs        REAL,
    fat          REAL
);
CREATE TABLE IF NOT EXISTS favourites (
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, recipe_id)
);
CREATE TABLE IF NOT EXISTS ratings (
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    stars     INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    PRIMARY KEY (user_id, recipe_id)
);
CREATE TABLE IF NOT EXISTS user_recipe_preferences (
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_key   TEXT NOT NULL,
    name         TEXT NOT NULL,
    ingredients  TEXT NOT NULL DEFAULT '[]',
    is_favorite  INTEGER NOT NULL DEFAULT 0,
    stars        INTEGER CHECK (stars BETWEEN 1 AND 5),
    PRIMARY KEY (user_id, recipe_key)
);
CREATE TABLE IF NOT EXISTS shopping_items (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    qty                REAL,
    unit               TEXT,
    cat                TEXT,
    bought             INTEGER NOT NULL DEFAULT 0,
    expiry_date        TEXT,
    source             TEXT NOT NULL DEFAULT 'manual',
    manual_quantity_base REAL,
    image             TEXT
);

-- Meal plan, water, health, profile (owner: K. K. Dilshan)
CREATE TABLE IF NOT EXISTS meal_plan (
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    meal      TEXT NOT NULL,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, day, meal)
);
CREATE TABLE IF NOT EXISTS water (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day     TEXT NOT NULL,
    glasses INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS health (
    user_id   INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    height_cm REAL,
    weight_kg REAL,
    target_kg REAL
);
CREATE TABLE IF NOT EXISTS weight_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    weight_kg REAL NOT NULL,
    logged_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT NOT NULL DEFAULT '',
    age           INTEGER,
    height        REAL,
    weight        REAL,
    allergies     TEXT NOT NULL DEFAULT '[]',
    health_notes  TEXT NOT NULL DEFAULT '',
    calorie_goal  INTEGER,
    target_weight REAL
);
"""

# Tables whose rows belong to one user. "Reset all data" clears these (the login stays).
USER_DATA_TABLES = [
    "pantry_items", "pantry", "dietary", "user_settings", "settings", "favourites", "ratings",
    "user_recipe_preferences",
    "shopping_items", "meal_plan", "water", "health", "weight_log", "profiles",
]

LEGACY_RECIPES = [
    ("Chickpea Salad Bowl", ["chickpeas", "cucumber", "tomato", "lemon"], "Mix the ingredients in a bowl and season with lemon.", "/assets/food/api-chickpea-salad.jpg"),
    ("Spinach Omelette", ["eggs", "spinach", "onion"], "Cook the onion and spinach, add beaten eggs, and cook until set.", "/assets/food/api-spinach-omelette.jpg"),
    ("Mango Yogurt Bowl", ["mango", "yogurt", "honey"], "Mix the mango and yogurt, then drizzle with honey.", "/assets/food/api-mango-yogurt.jpg"),
    ("Chicken Quinoa Bowl", ["chicken", "quinoa", "spinach", "lemon"], "Cook the quinoa and chicken, then serve with spinach and lemon.", "/assets/food/chicken-quinoa.jpg"),
    ("Baked Salmon with Vegetables", ["salmon", "broccoli", "lemon", "olive oil"], "Bake the salmon and broccoli with olive oil and lemon until cooked.", "/assets/food/baked-salmon.jpg"),
    ("Lentil Vegetable Soup", ["lentils", "carrot", "onion", "vegetable broth"], "Simmer the lentils and vegetables in broth until tender.", "/assets/food/lentil-soup.jpg"),
    ("Vegetable Rice Bowl", ["rice", "carrot", "peas"], "Cook the rice and vegetables, then serve together.", "/assets/food/vegetable-rice.jpeg"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    """Create all tables and seed the sample recipes (safe to run on every start)."""
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA)
        # Older databases made before this version only had users(id, name, email, password_hash).
        cols = {r[1] for r in db.execute("PRAGMA table_info(users)")}
        for col in ("recovery_hash", "picture"):
            if col not in cols:
                db.execute("ALTER TABLE users ADD COLUMN %s TEXT" % col)
        profile_cols = {r[1] for r in db.execute("PRAGMA table_info(profiles)")}
        profile_migrations = {
            "name": "TEXT NOT NULL DEFAULT ''",
            "height": "REAL",
            "weight": "REAL",
            "allergies": "TEXT NOT NULL DEFAULT '[]'",
            "target_weight": "REAL",
        }
        for col, definition in profile_migrations.items():
            if col not in profile_cols:
                db.execute("ALTER TABLE profiles ADD COLUMN %s %s" % (col, definition))
        shopping_cols = {r[1] for r in db.execute("PRAGMA table_info(shopping_items)")}
        shopping_migrations = {
            "expiry_date": "TEXT",
            "source": "TEXT NOT NULL DEFAULT 'manual'",
            "manual_quantity_base": "REAL",
            "image": "TEXT",
        }
        for col, definition in shopping_migrations.items():
            if col not in shopping_cols:
                db.execute("ALTER TABLE shopping_items ADD COLUMN %s %s" % (col, definition))
        db.execute(
            "UPDATE profiles SET allergies = (SELECT dietary.allergies FROM dietary "
            "WHERE dietary.user_id = profiles.user_id) "
            "WHERE EXISTS (SELECT 1 FROM dietary WHERE dietary.user_id = profiles.user_id)"
        )
        pantry_cols = {r[1] for r in db.execute("PRAGMA table_info(pantry)")}
        if "category" not in pantry_cols:
            db.execute("ALTER TABLE pantry ADD COLUMN category TEXT NOT NULL DEFAULT 'Other'")
        db.execute(
            "INSERT INTO pantry (user_id, name, category, quantity, unit, expiry_date) "
            "SELECT old.user_id, MIN(old.name), MIN(old.cat), SUM(old.qty), old.unit, MIN(old.exp) "
            "FROM pantry_items AS old "
            "WHERE NOT EXISTS (SELECT 1 FROM pantry AS new "
            "WHERE new.user_id = old.user_id AND lower(new.name) = lower(old.name) "
            "AND new.unit = old.unit) "
            "GROUP BY old.user_id, lower(old.name), old.unit"
        )
        if db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0:
            for name, ing, ins, img in LEGACY_RECIPES:
                db.execute(
                    "INSERT INTO recipes (name, ingredients, instructions, image) VALUES (?,?,?,?)",
                    (name, json.dumps(ing), ins, img),
                )


def import_recipes_json(db_path, json_path):
    """Recipes that were saved in recipes.json by the old Flask code are copied into the database once."""
    import os
    if not os.path.exists(json_path):
        return
    try:
        with open(json_path, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(saved, list):
        return
    with closing(sqlite3.connect(db_path)) as db, db:
        for r in saved:
            name = str(r.get("name") or "").strip()
            if not name or db.execute("SELECT 1 FROM recipes WHERE name = ?", (name,)).fetchone():
                continue
            db.execute("INSERT INTO recipes (name, ingredients, instructions, image) VALUES (?,?,?,?)",
                       (name, json.dumps(r.get("ingredients") or []), str(r.get("instructions") or ""), r.get("image") or ""))


def seed_new_user(db, user_id):
    """Give a fresh account the same sample pantry the front end used to show on first run."""
    today = date.today()
    sample = [
        ("Basmati rice", "Grains", 2, "kg", None),
        ("Carrots", "Vegetables", 6, "pcs", today + timedelta(days=2)),
        ("Milk", "Dairy", 1, "l", today + timedelta(days=1)),
        ("Eggs", "Protein", 10, "pcs", today + timedelta(days=9)),
    ]
    for name, cat, qty, unit, exp in sample:
        db.execute(
            "INSERT INTO pantry (user_id, name, category, quantity, unit, expiry_date) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, name, cat, qty, unit, exp.isoformat() if exp else None),
        )
    from services.pantry_service import sync_legacy_items
    sync_legacy_items(db, user_id)
