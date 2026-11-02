"""
Database helpers shared by every API module.

- get_db()      -> per-request SQLite connection (stored on flask.g)
- init_schema() -> creates the app tables (safe to run on every start)

The `users` table is still created by app.py (init_db). New feature tables are
added here, one block per phase, using CREATE TABLE IF NOT EXISTS.
"""
import os
import sqlite3

from flask import g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# VITAPLATE_DB lets the tests use a throw-away database file.
DB_PATH = os.environ.get("VITAPLATE_DB") or os.path.join(BASE_DIR, "vitaplate.db")

SCHEMA = """
-- Phase 1: pantry (requirement 1)
CREATE TABLE IF NOT EXISTS pantry_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'Other',
    quantity    REAL NOT NULL CHECK (quantity > 0),
    unit        TEXT NOT NULL DEFAULT 'pcs',
    expiry_date TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- one row per ingredient name for each user (case-insensitive)
CREATE UNIQUE INDEX IF NOT EXISTS idx_pantry_user_name
    ON pantry_items (user_id, name COLLATE NOCASE);

-- Phase 2: recipes, favourites, ratings (requirements 3, 5, 6)
-- The recipe catalogue is shared by all users; favourites and ratings belong to one user.
CREATE TABLE IF NOT EXISTS recipes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    instructions TEXT NOT NULL DEFAULT '',
    image        TEXT,
    time_minutes INTEGER,
    kcal         INTEGER,
    protein      REAL,
    carbs        REAL,
    fat          REAL,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    name      TEXT NOT NULL,
    PRIMARY KEY (recipe_id, position)
);
CREATE TABLE IF NOT EXISTS recipe_diets (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    diet      TEXT NOT NULL,
    PRIMARY KEY (recipe_id, diet)
);
CREATE TABLE IF NOT EXISTS favorites (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, recipe_id)
);
CREATE TABLE IF NOT EXISTS ratings (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    stars      INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, recipe_id)
);
"""


def get_db():
    """Return the SQLite connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_schema():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)
