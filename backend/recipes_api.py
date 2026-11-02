"""
Recipes, favourites and ratings API
(Functional requirements 3 browse/search, 5 favourites, 6 ratings)

All routes need a logged-in user. The recipe catalogue is shared by everybody;
favourites and ratings belong to the logged-in user.

    GET    /api/recipes                    list/search       ?q=text  &diet=Vegan&diet=Halal
    GET    /api/recipes/<id>               one recipe
    POST   /api/recipes                    add a recipe      (multipart form, see create_recipe)
    PUT    /api/recipes/<id>/favorite      add to my favourites
    DELETE /api/recipes/<id>/favorite      remove from my favourites
    GET    /api/favorites                  my favourite recipes
    POST   /api/favorites/import           {recipe_ids: [..]}      (one-off migration)
    PUT    /api/recipes/<id>/rating        {stars: 1-5}
    DELETE /api/recipes/<id>/rating        remove my rating
    POST   /api/ratings/import             {ratings: {"3": 4}}     (one-off migration)

Recipe JSON:
    {id, name, image, time, kcal, protein, carbs, fat, diets[], ingredients[], instructions,
     avg_rating, rating_count, my_rating, is_favorite}
    time/kcal/protein/carbs/fat are null when the recipe has no value;
    my_rating is 0 when the user has not rated it; avg_rating is null until someone rates it.
"""
import math
import os
import secrets
import time

from flask import Blueprint, jsonify, request

from auth_utils import current_user_id, login_required
from database import get_db

recipes_bp = Blueprint("recipes", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Uploaded photos go next to the other food photos so the static server can show them.
# VITAPLATE_UPLOAD_DIR lets the tests use a temporary folder.
UPLOAD_DIR = os.environ.get("VITAPLATE_UPLOAD_DIR") or os.path.join(
    os.path.dirname(BASE_DIR), "vitaplate", "assets", "food"
)
IMAGE_URL_PREFIX = "assets/food/"

DIETS = ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Nut-free", "Halal", "Low sugar"]
DIET_LOOKUP = {diet.lower(): diet for diet in DIETS}

MAX_NAME_LENGTH = 80
MAX_INSTRUCTIONS_LENGTH = 3000
MAX_INGREDIENTS = 40
MAX_INGREDIENT_LENGTH = 60
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_IMAGE_BYTES + 1024 * 1024  # photo + text fields


class ValidationError(Exception):
    """The request contained a bad value (HTTP 400)."""


# ----------------------------------------------------------------- helpers
def error(message, status=400):
    return jsonify({"error": message}), status


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def clean_number(value):
    return int(value) if float(value).is_integer() else value


# -------------------------------------------------------------- validation
def parse_name(value):
    name = " ".join(str(value or "").split())
    if not name:
        raise ValidationError("Enter a recipe name")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"Recipe name must be {MAX_NAME_LENGTH} characters or fewer")
    return name


def parse_ingredients(value):
    """'rice, carrot,Peas' -> ['rice', 'carrot', 'Peas'] (no empty or repeated names)."""
    seen, ingredients = set(), []
    for part in str(value or "").split(","):
        item = " ".join(part.split())
        if item and item.lower() not in seen:
            seen.add(item.lower())
            ingredients.append(item)
    if not ingredients:
        raise ValidationError("Add at least one ingredient")
    if len(ingredients) > MAX_INGREDIENTS:
        raise ValidationError(f"Use {MAX_INGREDIENTS} ingredients or fewer")
    if any(len(item) > MAX_INGREDIENT_LENGTH for item in ingredients):
        raise ValidationError(f"Each ingredient must be {MAX_INGREDIENT_LENGTH} characters or fewer")
    return ingredients


def parse_instructions(value):
    text = str(value or "").strip()
    if not text:
        raise ValidationError("Add the instructions")
    if len(text) > MAX_INSTRUCTIONS_LENGTH:
        raise ValidationError(f"Instructions must be {MAX_INSTRUCTIONS_LENGTH} characters or fewer")
    return text


def parse_optional_number(value, label, minimum, maximum, whole=False):
    """Blank -> None. Otherwise a number between minimum and maximum."""
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a number")
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise ValidationError(f"{label} must be between {minimum} and {maximum}")
    return int(round(number)) if whole else round(number, 1)


def parse_diets(values):
    diets = []
    for value in values:
        canonical = DIET_LOOKUP.get(str(value).strip().lower())
        if canonical is None:
            raise ValidationError(f"Unknown diet tag: {value}")
        if canonical not in diets:
            diets.append(canonical)
    return diets


def sniff_image_extension(data):
    """Decide the image type from the file content, not from the file name."""
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def read_image(upload):
    """Return (bytes, extension) for the uploaded photo or raise ValidationError."""
    if upload is None or not upload.filename:
        raise ValidationError("Add a photo of the dish")
    data = upload.stream.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("Choose a photo smaller than 5 MB.")
    extension = sniff_image_extension(data)
    if extension is None:
        raise ValidationError("Choose a JPG, PNG, or WebP image.")
    return data, extension


# --------------------------------------------------------------- reading
RECIPE_SQL = """
SELECT r.*,
       (SELECT AVG(stars)  FROM ratings WHERE recipe_id = r.id)                    AS avg_rating,
       (SELECT COUNT(*)    FROM ratings WHERE recipe_id = r.id)                    AS rating_count,
       (SELECT stars       FROM ratings WHERE recipe_id = r.id AND user_id = ?)    AS my_rating,
       EXISTS (SELECT 1 FROM favorites WHERE recipe_id = r.id AND user_id = ?)     AS is_favorite
FROM recipes r
"""


def fetch_recipes(db, user_id, recipe_id=None, favorites_only=False):
    """Recipes as dictionaries, with ingredients, diet tags and this user's rating/favourite."""
    sql, params, where = RECIPE_SQL, [user_id, user_id], []
    if recipe_id is not None:
        where.append("r.id = ?")
        params.append(recipe_id)
    if favorites_only:
        where.append("EXISTS (SELECT 1 FROM favorites WHERE recipe_id = r.id AND user_id = ?)")
        params.append(user_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = db.execute(sql + " ORDER BY r.id", params).fetchall()
    if not rows:
        return []

    ids = [row["id"] for row in rows]
    marks = ",".join("?" * len(ids))
    ingredients = {rid: [] for rid in ids}
    for row in db.execute(
        f"SELECT recipe_id, name FROM recipe_ingredients WHERE recipe_id IN ({marks}) ORDER BY recipe_id, position", ids
    ):
        ingredients[row["recipe_id"]].append(row["name"])
    diets = {rid: [] for rid in ids}
    for row in db.execute(
        f"SELECT recipe_id, diet FROM recipe_diets WHERE recipe_id IN ({marks}) ORDER BY recipe_id, diet", ids
    ):
        diets[row["recipe_id"]].append(row["diet"])

    result = []
    for row in rows:
        number = lambda column: None if row[column] is None else clean_number(row[column])  # noqa: E731
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "image": row["image"],
                "time": number("time_minutes"),
                "kcal": number("kcal"),
                "protein": number("protein"),
                "carbs": number("carbs"),
                "fat": number("fat"),
                "diets": diets[row["id"]],
                "ingredients": ingredients[row["id"]],
                "instructions": row["instructions"],
                "avg_rating": None if row["avg_rating"] is None else round(row["avg_rating"], 1),
                "rating_count": row["rating_count"],
                "my_rating": row["my_rating"] or 0,
                "is_favorite": bool(row["is_favorite"]),
            }
        )
    return result


def recipe_exists(db, recipe_id):
    return db.execute("SELECT 1 FROM recipes WHERE id = ?", (recipe_id,)).fetchone() is not None


def rating_summary(db, user_id, recipe_id):
    row = db.execute(
        """SELECT (SELECT AVG(stars) FROM ratings WHERE recipe_id = ?) AS avg_rating,
                  (SELECT COUNT(*)   FROM ratings WHERE recipe_id = ?) AS rating_count,
                  (SELECT stars      FROM ratings WHERE recipe_id = ? AND user_id = ?) AS my_rating""",
        (recipe_id, recipe_id, recipe_id, user_id),
    ).fetchone()
    return {
        "avg_rating": None if row["avg_rating"] is None else round(row["avg_rating"], 1),
        "rating_count": row["rating_count"],
        "my_rating": row["my_rating"] or 0,
    }


# ----------------------------------------------------------- recipe routes
@recipes_bp.get("/api/recipes")
@login_required
def list_recipes():
    wanted_diets = []
    for value in request.args.getlist("diet"):
        canonical = DIET_LOOKUP.get(value.strip().lower())
        if canonical is None:
            return error(f"Unknown diet tag: {value}")
        wanted_diets.append(canonical)
    text = request.args.get("q", "").strip().lower()

    recipes = fetch_recipes(get_db(), current_user_id())
    if text:
        recipes = [
            r for r in recipes if text in r["name"].lower() or any(text in item.lower() for item in r["ingredients"])
        ]
    if wanted_diets:  # a recipe must have every requested tag
        recipes = [r for r in recipes if all(diet in r["diets"] for diet in wanted_diets)]
    return jsonify({"recipes": recipes})


@recipes_bp.get("/api/recipes/<int:recipe_id>")
@login_required
def get_recipe(recipe_id):
    found = fetch_recipes(get_db(), current_user_id(), recipe_id=recipe_id)
    if not found:
        return error("Recipe not found", 404)
    return jsonify({"recipe": found[0]})


@recipes_bp.post("/api/recipes")
@login_required
def create_recipe():
    """
    Multipart form fields:  name, ingredients (comma separated), instructions, imageFile (JPG/PNG/WebP, max 5 MB)
    optional:               time (minutes), kcal, protein, carbs, fat, diet (repeat the field for each tag)
    """
    if request.content_length and request.content_length > MAX_REQUEST_BYTES:
        return error("Choose a photo smaller than 5 MB.", 413)

    form = request.form
    try:
        name = parse_name(form.get("name"))
        ingredients = parse_ingredients(form.get("ingredients"))
        instructions = parse_instructions(form.get("instructions"))
        minutes = parse_optional_number(form.get("time"), "Prep time", 1, 1440, whole=True)
        kcal = parse_optional_number(form.get("kcal"), "Calories", 0, 5000, whole=True)
        protein = parse_optional_number(form.get("protein"), "Protein", 0, 1000)
        carbs = parse_optional_number(form.get("carbs"), "Carbs", 0, 1000)
        fat = parse_optional_number(form.get("fat"), "Fat", 0, 1000)
        diets = parse_diets(form.getlist("diet"))
        image_bytes, extension = read_image(request.files.get("imageFile"))
    except ValidationError as exc:
        return error(str(exc))

    # everything is valid: save the photo, then the rows (remove the photo again if that fails)
    filename = f"recipe-{int(time.time() * 1000)}-{secrets.token_hex(4)}{extension}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as handle:
        handle.write(image_bytes)

    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO recipes (name, instructions, image, time_minutes, kcal, protein, carbs, fat, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, instructions, IMAGE_URL_PREFIX + filename, minutes, kcal, protein, carbs, fat, current_user_id()),
        )
        recipe_id = cur.lastrowid
        db.executemany(
            "INSERT INTO recipe_ingredients (recipe_id, position, name) VALUES (?, ?, ?)",
            [(recipe_id, position, item) for position, item in enumerate(ingredients)],
        )
        db.executemany("INSERT INTO recipe_diets (recipe_id, diet) VALUES (?, ?)", [(recipe_id, d) for d in diets])
        db.commit()
    except Exception:
        db.rollback()
        os.remove(path)
        raise
    return jsonify({"recipe": fetch_recipes(db, current_user_id(), recipe_id=recipe_id)[0]}), 201


# -------------------------------------------------------------- favourites
@recipes_bp.put("/api/recipes/<int:recipe_id>/favorite")
@login_required
def add_favorite(recipe_id):
    db = get_db()
    if not recipe_exists(db, recipe_id):
        return error("Recipe not found", 404)
    db.execute("INSERT OR IGNORE INTO favorites (user_id, recipe_id) VALUES (?, ?)", (current_user_id(), recipe_id))
    db.commit()
    return jsonify({"is_favorite": True})


@recipes_bp.delete("/api/recipes/<int:recipe_id>/favorite")
@login_required
def remove_favorite(recipe_id):
    db = get_db()
    if not recipe_exists(db, recipe_id):
        return error("Recipe not found", 404)
    db.execute("DELETE FROM favorites WHERE user_id = ? AND recipe_id = ?", (current_user_id(), recipe_id))
    db.commit()
    return jsonify({"is_favorite": False})


@recipes_bp.get("/api/favorites")
@login_required
def list_favorites():
    return jsonify({"recipes": fetch_recipes(get_db(), current_user_id(), favorites_only=True)})


@recipes_bp.post("/api/favorites/import")
@login_required
def import_favorites():
    """Move favourites that were saved in the browser into the database (unknown ids are skipped)."""
    ids = body().get("recipe_ids")
    if not isinstance(ids, list) or len(ids) > 500:
        return error("Send a list called 'recipe_ids'")
    db = get_db()
    imported = 0
    for value in ids:
        if isinstance(value, bool) or not isinstance(value, int) or not recipe_exists(db, value):
            continue
        cur = db.execute(
            "INSERT OR IGNORE INTO favorites (user_id, recipe_id) VALUES (?, ?)", (current_user_id(), value)
        )
        imported += cur.rowcount
    db.commit()
    return jsonify({"imported": imported})


# ----------------------------------------------------------------- ratings
@recipes_bp.put("/api/recipes/<int:recipe_id>/rating")
@login_required
def set_rating(recipe_id):
    db = get_db()
    if not recipe_exists(db, recipe_id):
        return error("Recipe not found", 404)
    stars = body().get("stars")
    if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
        return error("Rate from 1 to 5 stars")
    db.execute(
        """INSERT INTO ratings (user_id, recipe_id, stars) VALUES (?, ?, ?)
           ON CONFLICT (user_id, recipe_id) DO UPDATE SET stars = excluded.stars, updated_at = CURRENT_TIMESTAMP""",
        (current_user_id(), recipe_id, stars),
    )
    db.commit()
    return jsonify(rating_summary(db, current_user_id(), recipe_id))


@recipes_bp.delete("/api/recipes/<int:recipe_id>/rating")
@login_required
def remove_rating(recipe_id):
    db = get_db()
    if not recipe_exists(db, recipe_id):
        return error("Recipe not found", 404)
    db.execute("DELETE FROM ratings WHERE user_id = ? AND recipe_id = ?", (current_user_id(), recipe_id))
    db.commit()
    return jsonify(rating_summary(db, current_user_id(), recipe_id))


@recipes_bp.post("/api/ratings/import")
@login_required
def import_ratings():
    """Move ratings saved in the browser into the database. Ratings you already made are kept."""
    ratings = body().get("ratings")
    if not isinstance(ratings, dict) or len(ratings) > 500:
        return error("Send an object called 'ratings'")
    db = get_db()
    imported = 0
    for key, stars in ratings.items():
        try:
            recipe_id = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5 or not recipe_exists(db, recipe_id):
            continue
        cur = db.execute(
            "INSERT OR IGNORE INTO ratings (user_id, recipe_id, stars) VALUES (?, ?, ?)",
            (current_user_id(), recipe_id, stars),
        )
        imported += cur.rowcount
    db.commit()
    return jsonify({"imported": imported})
