import sqlite3

from db import init_db


def test_init_db_migrates_user_schema_and_legacy_pantry(tmp_path):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            INSERT INTO users (name, email, password_hash)
            VALUES ('Test User', 'test@example.com', 'hash');
            CREATE TABLE profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                age INTEGER,
                calorie_goal INTEGER,
                health_notes TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE pantry_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                cat TEXT NOT NULL DEFAULT 'Other',
                qty REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT 'pcs',
                exp TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO pantry_items (user_id, name, cat, qty, unit, exp)
            VALUES (1, 'Beans', 'Protein', 2, 'kg', '2030-02-01'),
                   (1, 'BEANS', 'Protein', 3, 'kg', '2030-01-01');
        """)
        connection.commit()
    finally:
        connection.close()

    init_db(str(database))
    connection = sqlite3.connect(database)
    try:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"profiles", "dietary", "pantry", "settings"} <= tables

        profile_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(profiles)")
        }
        assert {
            "name", "age", "height", "weight", "allergies", "health_notes",
            "calorie_goal", "target_weight",
        } <= profile_columns

        pantry = connection.execute(
            "SELECT name, category, quantity, unit, expiry_date FROM pantry"
        ).fetchone()
        assert pantry == ("BEANS", "Protein", 5.0, "kg", "2030-01-01")

        for table in ("profiles", "dietary", "pantry", "settings"):
            foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(%s)" % table).fetchall()
            assert any(
                key[2] == "users" and key[3] == "user_id" and key[6] == "CASCADE"
                for key in foreign_keys
            ), table
    finally:
        connection.close()
