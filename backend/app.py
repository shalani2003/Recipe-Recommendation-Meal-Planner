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
import json
from uuid import uuid4
from datetime import timedelta

from flask import Flask, g, jsonify, redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "vitaplate")
DB_PATH = os.path.join(BASE_DIR, "vitaplate.db")
KEY_PATH = os.path.join(BASE_DIR, "secret.key")
RECIPE_STORE_PATH = os.path.join(BASE_DIR, "recipes.json")
RECIPE_IMAGE_DIR = os.path.join(FRONTEND_DIR, "assets", "food")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_RECIPE_IMAGE_BYTES = 5 * 1024 * 1024


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


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in {"http://127.0.0.1:3000", "http://localhost:3000", "http://127.0.0.1:5000"}:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


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
    return jsonify({"success": False, "message": message, "error": message}), status


BUILTIN_RECIPES = [
    {"id": 1, "name": "Chickpea Salad Bowl", "ingredients": ["chickpeas", "cucumber", "tomato", "lemon"], "instructions": "Mix the ingredients in a bowl and season with lemon.", "image": "/assets/food/api-chickpea-salad.jpg"},
    {"id": 2, "name": "Spinach Omelette", "ingredients": ["eggs", "spinach", "onion"], "instructions": "Cook the onion and spinach, add beaten eggs, and cook until set.", "image": "/assets/food/api-spinach-omelette.jpg"},
    {"id": 3, "name": "Mango Yogurt Bowl", "ingredients": ["mango", "yogurt", "honey"], "instructions": "Mix the mango and yogurt, then drizzle with honey.", "image": "/assets/food/api-mango-yogurt.jpg"},
    {"id": 4, "name": "Chicken Quinoa Bowl", "ingredients": ["chicken", "quinoa", "spinach", "lemon"], "instructions": "Cook the quinoa and chicken, then serve with spinach and lemon.", "image": "/assets/food/chicken-quinoa.jpg"},
    {"id": 5, "name": "Baked Salmon with Vegetables", "ingredients": ["salmon", "broccoli", "lemon", "olive oil"], "instructions": "Bake the salmon and broccoli with olive oil and lemon until cooked.", "image": "/assets/food/baked-salmon.jpg"},
    {"id": 6, "name": "Lentil Vegetable Soup", "ingredients": ["lentils", "carrot", "onion", "vegetable broth"], "instructions": "Simmer the lentils and vegetables in broth until tender.", "image": "/assets/food/lentil-soup.jpg"},
    {"id": 7, "name": "Vegetable Rice Bowl", "ingredients": ["rice", "carrot", "peas"], "instructions": "Cook the rice and vegetables, then serve together.", "image": "/assets/food/vegetable-rice.jpeg"},
]


def load_saved_recipes():
    if not os.path.exists(RECIPE_STORE_PATH):
        return []
    try:
        with open(RECIPE_STORE_PATH, encoding="utf-8") as recipe_file:
            data = json.load(recipe_file)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_user_recipes(recipes):
    with open(RECIPE_STORE_PATH, "w", encoding="utf-8") as recipe_file:
        json.dump(recipes, recipe_file, indent=2)


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


@app.get("/api/recipes")
def recipes():
    return jsonify(BUILTIN_RECIPES + load_saved_recipes())


@app.post("/api/recipes")
def create_recipe():
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        name = request.form.get("name", "").strip()
        raw_ingredients = request.form.get("ingredients", "")
        instructions = request.form.get("instructions", "").strip()
        image = request.files.get("imageFile")
    else:
        data = body()
        name = str(data.get("name") or "").strip()
        raw_ingredients = data.get("ingredients", "")
        instructions = str(data.get("instructions") or "").strip()
        image = None

    ingredients = raw_ingredients if isinstance(raw_ingredients, list) else str(raw_ingredients).split(",")
    ingredients = [item.strip() for item in ingredients if item and item.strip()]
    if not name:
        return error("Recipe name is required")
    if not ingredients:
        return error("At least one ingredient is required")
    if not instructions:
        return error("Instructions are required")

    image_path = ""
    if image and image.filename:
        extension = os.path.splitext(image.filename)[1].lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            return error("Choose a JPG, PNG, or WebP image.")
        image.stream.seek(0, os.SEEK_END)
        if image.stream.tell() > MAX_RECIPE_IMAGE_BYTES:
            return error("Choose a photo smaller than 5 MB.")
        image.stream.seek(0)
        os.makedirs(RECIPE_IMAGE_DIR, exist_ok=True)
        filename = f"recipe-{uuid4().hex}{extension}"
        image.save(os.path.join(RECIPE_IMAGE_DIR, filename))
        image_path = f"/assets/food/{filename}"

    saved_recipes = load_saved_recipes()
    new_recipe = {
        "id": max([7, *[int(item.get("id", 0)) for item in saved_recipes]]) + 1,
        "name": name,
        "ingredients": ingredients,
        "instructions": instructions,
        "image": image_path,
    }
    saved_recipes.append(new_recipe)
    try:
        save_user_recipes(saved_recipes)
    except OSError:
        if image_path:
            try:
                os.remove(os.path.join(FRONTEND_DIR, image_path.lstrip("/").replace("/", os.sep)))
            except OSError:
                pass
        return error("The recipe could not be saved.", 500)

    return jsonify({
        "success": True,
        "message": "Recipe saved successfully",
        "recipe": new_recipe,
    }), 201


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return error("Not found", 404)
    return "Page not found", 404


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
