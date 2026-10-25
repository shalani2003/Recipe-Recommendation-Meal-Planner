"""
VitaPlate backend (Flask + SQLite)
- Serves the ../vitaplate frontend files
- API: /api/register, /api/login, /api/logout, /api/me, /api/reset-password
Run:  python app.py   ->  http://127.0.0.1:5000
"""
import os
import re
import secrets
import sqlite3
from datetime import timedelta

from flask import Flask, g, jsonify, redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "vitaplate")
DB_PATH = os.path.join(BASE_DIR, "vitaplate.db")
KEY_PATH = os.path.join(BASE_DIR, "secret.key")


def load_secret_key():
    """Keep one secret key between restarts so logins stay valid."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if not os.path.exists(KEY_PATH):
        with open(KEY_PATH, "w") as f:
            f.write(secrets.token_hex(32))
    with open(KEY_PATH) as f:
        return f.read().strip()


app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


# ----------------------------------------------------------------- helpers
def error(message, status=400):
    return jsonify({"error": message}), status


def body():
    return request.get_json(silent=True) or {}


def clean_email(value):
    return str(value or "").strip().lower()


def password_problem(pw):
    if len(pw) < 8 or not re.search(r"\d", pw):
        return "Use 8+ characters with at least one number"
    return None


def public_user(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def login_user(row):
    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]


# ------------------------------------------------------------------ routes
@app.route("/")
def home():
    return redirect("/login.html")


@app.post("/api/register")
def register():
    data = body()
    name = str(data.get("name") or "").strip()
    email = clean_email(data.get("email"))
    pw = str(data.get("password") or "")

    if len(name) < 2:
        return error("Enter your name")
    if not EMAIL_RE.match(email):
        return error("Enter a valid email")
    problem = password_problem(pw)
    if problem:
        return error(problem)

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        return error("An account with this email already exists. Try logging in.", 409)

    cur = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(pw)),
    )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    login_user(row)
    return jsonify({"user": public_user(row)}), 201


@app.post("/api/login")
def login():
    data = body()
    email = clean_email(data.get("email"))
    pw = str(data.get("password") or "")

    if not EMAIL_RE.match(email):
        return error("Enter a valid email")
    if not pw:
        return error("Enter your password")

    row = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], pw):
        return error("Email or password is incorrect.", 401)

    login_user(row)
    return jsonify({"user": public_user(row)})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    uid = session.get("user_id")
    if uid is None:
        return error("Not logged in", 401)
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None:
        session.clear()
        return error("Not logged in", 401)
    return jsonify({"user": public_user(row)})


@app.post("/api/reset-password")
def reset_password():
    data = body()
    email = clean_email(data.get("email"))
    pw = str(data.get("password") or "")

    if not EMAIL_RE.match(email):
        return error("Enter a valid email")
    problem = password_problem(pw)
    if problem:
        return error(problem)

    db = get_db()
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        return error("No account was found with that email.", 404)

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(pw), row["id"]),
    )
    db.commit()
    return jsonify({"ok": True})


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return error("Not found", 404)
    return "Page not found", 404


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
