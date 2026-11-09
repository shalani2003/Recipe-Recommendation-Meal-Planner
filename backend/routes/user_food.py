"""Persist user favorites, ratings, and meal plans."""
import json
import hashlib
import re

from flask import Blueprint, g, jsonify

from auth_helpers import body, error, login_required
from db import get_db

bp = Blueprint("user_food", __name__, url_prefix="/api")
DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
MEALS = {"Breakfast", "Lunch", "Dinner"}
BAD_RECIPE_NAME = re.compile(r"[<>\x00-\x1f]")


def recipe_from_payload(db, data, user_id, create=True):
    if not isinstance(data, dict):
        return None, "A recipe object is required"
    name = data.get("name")
    if not isinstance(name, str):
        return None, "Recipe name must be text"
    name = " ".join(name.split())
    if not name or len(name) > 80 or BAD_RECIPE_NAME.search(name):
        return None, "Recipe name must be 1 to 80 characters of plain text"
    ingredients = data.get("ingredients", data.get("ing", []))
    if not isinstance(ingredients, list) or any(
        not isinstance(item, str) or len(item) > 100 for item in ingredients
    ):
        return None, "Recipe ingredients must be a list of text values"
    cleaned = [" ".join(item.split()) for item in ingredients]
    if len(cleaned) > 100:
        return None, "A recipe can have up to 100 ingredients"

    # API recipe IDs are namespaced in the browser to avoid collisions with the
    # separate built-in recipe IDs. Resolve those IDs directly when supplied.
    recipe_ref = data.get("id")
    if isinstance(recipe_ref, str) and recipe_ref.startswith("api:"):
        match = re.fullmatch(r"api:([1-9]\d*)", recipe_ref)
        if not match:
            return None, "Recipe ID is invalid"
        row = db.execute(
            "SELECT id, name, ingredients FROM recipes WHERE id = ? "
            "AND (owner_user_id IS NULL OR owner_user_id = ?)",
            (int(match.group(1)), user_id),
        ).fetchone()
        if row is None or row["name"].casefold() != name.casefold():
            return None, "Recipe not found"
        stored = json.loads(row["ingredients"] or "[]")
        if sorted(item.casefold() for item in stored) != sorted(item.casefold() for item in cleaned):
            return None, "Recipe ingredients do not match this recipe"
        return row["id"], None

    candidates = db.execute(
        "SELECT id, ingredients FROM recipes WHERE lower(name) = lower(?) "
        "AND (owner_user_id IS NULL OR owner_user_id = ?) ORDER BY id",
        (name, user_id),
    ).fetchall()
    wanted_ingredients = sorted(item.casefold() for item in cleaned)
    for row in candidates:
        stored = json.loads(row["ingredients"] or "[]")
        if sorted(item.casefold() for item in stored) == wanted_ingredients:
            return row["id"], None
    if not ingredients and len(candidates) == 1:
        return candidates[0]["id"], None
    if not create:
        return None, None
    if not ingredients and candidates:
        return None, "Recipe name is ambiguous; include its ingredients"

    cursor = db.execute(
        "INSERT INTO recipes (owner_user_id, name, ingredients, instructions) VALUES (?, ?, ?, ?)",
        (user_id, name, json.dumps(cleaned), ""),
    )
    return cursor.lastrowid, None


def meal_plan_json(db, user_id):
    rows = db.execute(
        "SELECT mp.day, mp.meal, mp.recipe_id, r.name AS recipe_name "
        "FROM meal_plan AS mp LEFT JOIN recipes AS r ON r.id = mp.recipe_id "
        "WHERE mp.user_id = ? ORDER BY mp.day, mp.meal",
        (user_id,),
    ).fetchall()
    return [
        {"day": row["day"], "meal": row["meal"], "recipe_id": row["recipe_id"],
         "recipe_name": row["recipe_name"]}
        for row in rows
    ]


def store_external_preference(db, user_id, data, *, favorite=None, stars=None):
    """Keep actions for non-catalog recipes on the user's own account record."""
    name = " ".join(data["name"].split())
    ingredients = [" ".join(item.split()) for item in data.get("ingredients", data.get("ing", []))]
    canonical = json.dumps(sorted(item.casefold() for item in ingredients), ensure_ascii=False)
    recipe_key = hashlib.sha256((name.casefold() + "\n" + canonical).encode("utf-8")).hexdigest()
    existing = db.execute(
        "SELECT is_favorite, stars FROM user_recipe_preferences WHERE user_id = ? AND recipe_key = ?",
        (user_id, recipe_key),
    ).fetchone()
    is_favorite = bool(existing["is_favorite"]) if existing else False
    current_stars = existing["stars"] if existing else None
    if favorite is not None:
        is_favorite = favorite
    if "stars" in data:
        current_stars = stars if stars else None
    if not is_favorite and current_stars is None:
        db.execute("DELETE FROM user_recipe_preferences WHERE user_id = ? AND recipe_key = ?", (user_id, recipe_key))
    else:
        db.execute(
            "INSERT INTO user_recipe_preferences (user_id, recipe_key, name, ingredients, is_favorite, stars) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, recipe_key) DO UPDATE SET "
            "name=excluded.name, ingredients=excluded.ingredients, is_favorite=excluded.is_favorite, stars=excluded.stars",
            (user_id, recipe_key, name, json.dumps(ingredients), int(is_favorite), current_stars),
        )
    return recipe_key


@bp.get("/favorites")
@bp.get("/favourites")
@login_required
def list_favorites():
    db = get_db()
    rows = db.execute(
        "SELECT r.name FROM favourites AS f JOIN recipes AS r ON r.id = f.recipe_id "
        "WHERE f.user_id = ? ORDER BY lower(r.name)",
        (g.user_id,),
    ).fetchall()
    external = db.execute(
        "SELECT name FROM user_recipe_preferences WHERE user_id = ? AND is_favorite = 1 ORDER BY lower(name)",
        (g.user_id,),
    ).fetchall()
    return jsonify({"favorites": [row["name"] for row in rows] + [row["name"] for row in external]})


@bp.get("/favorites/records")
@login_required
def list_favorite_records():
    db = get_db()
    rows = db.execute(
        "SELECT r.id, r.name, r.ingredients FROM favourites AS f "
        "JOIN recipes AS r ON r.id = f.recipe_id "
        "WHERE f.user_id = ? ORDER BY lower(r.name), r.id",
        (g.user_id,),
    ).fetchall()
    records = [
        {"id": row["id"], "name": row["name"], "ingredients": json.loads(row["ingredients"] or "[]")}
        for row in rows
    ]
    external = db.execute(
        "SELECT recipe_key, name, ingredients FROM user_recipe_preferences "
        "WHERE user_id = ? AND is_favorite = 1 ORDER BY lower(name), recipe_key",
        (g.user_id,),
    ).fetchall()
    records.extend({"id": "external:" + row["recipe_key"], "name": row["name"],
                    "ingredients": json.loads(row["ingredients"] or "[]")} for row in external)
    return jsonify({"records": records})


@bp.post("/favorites")
@bp.post("/favourites")
@login_required
def add_favorite():
    db = get_db()
    recipe_id, problem = recipe_from_payload(db, body(), g.user_id, create=False)
    if problem:
        return error(problem)
    if recipe_id is None:
        store_external_preference(db, g.user_id, body(), favorite=True)
        db.commit()
        return jsonify({"ok": True}), 201
    db.execute(
        "INSERT OR IGNORE INTO favourites (user_id, recipe_id) VALUES (?, ?)",
        (g.user_id, recipe_id),
    )
    db.commit()
    return jsonify({"ok": True}), 201


@bp.delete("/favorites")
@bp.delete("/favourites")
@login_required
def remove_favorite():
    db = get_db()
    recipe_id, problem = recipe_from_payload(db, body(), g.user_id, create=False)
    if problem:
        return error(problem)
    if recipe_id is not None:
        db.execute(
            "DELETE FROM favourites WHERE user_id = ? AND recipe_id = ?",
            (g.user_id, recipe_id),
        )
        db.commit()
    else:
        store_external_preference(db, g.user_id, body(), favorite=False)
        db.commit()
    return jsonify({"ok": True})


@bp.get("/ratings")
@login_required
def list_ratings():
    db = get_db()
    rows = db.execute(
        "SELECT r.name, rt.stars FROM ratings AS rt JOIN recipes AS r ON r.id = rt.recipe_id "
        "WHERE rt.user_id = ?",
        (g.user_id,),
    ).fetchall()
    ratings = {row["name"]: row["stars"] for row in rows}
    external = db.execute(
        "SELECT name, stars FROM user_recipe_preferences WHERE user_id = ? AND stars IS NOT NULL",
        (g.user_id,),
    ).fetchall()
    ratings.update({row["name"]: row["stars"] for row in external})
    return jsonify({"ratings": ratings})


@bp.put("/ratings")
@login_required
def save_rating():
    data = body()
    if not isinstance(data, dict):
        return error("Rating must be a JSON object")
    stars = data.get("stars")
    if isinstance(stars, bool) or not isinstance(stars, int) or not 0 <= stars <= 5:
        return error("Rating must be a whole number from 0 to 5")

    db = get_db()
    if stars == 0:
        recipe_id, problem = recipe_from_payload(db, data, g.user_id, create=False)
        if problem:
            return error(problem)
        if recipe_id is not None:
            db.execute(
                "DELETE FROM ratings WHERE user_id = ? AND recipe_id = ?",
                (g.user_id, recipe_id),
            )
            db.commit()
        else:
            store_external_preference(db, g.user_id, data, stars=0)
            db.commit()
        return jsonify({"ok": True})

    recipe_id, problem = recipe_from_payload(db, data, g.user_id, create=False)
    if problem:
        return error(problem)
    if recipe_id is None:
        store_external_preference(db, g.user_id, data, stars=stars)
        db.commit()
        return jsonify({"ok": True})
    db.execute(
        "INSERT INTO ratings (user_id, recipe_id, stars) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, recipe_id) DO UPDATE SET stars = excluded.stars",
        (g.user_id, recipe_id, stars),
    )
    db.commit()
    return jsonify({"ok": True})


@bp.get("/meal-plan")
@login_required
def get_meal_plan():
    return jsonify({"meals": meal_plan_json(get_db(), g.user_id)})


@bp.put("/meal-plan")
@login_required
def save_meal_plan():
    data = body()
    if not isinstance(data, dict) or not isinstance(data.get("meals"), list):
        return error("meals must be a list")
    if len(data["meals"]) > len(DAYS) * len(MEALS):
        return error("A weekly plan can contain at most 21 meals")

    db = get_db()
    entries = []
    seen = set()
    for entry in data["meals"]:
        if not isinstance(entry, dict):
            return error("Each planned meal must be an object")
        day, meal = entry.get("day"), entry.get("meal")
        if not isinstance(day, str) or not isinstance(meal, str) or day not in DAYS or meal not in MEALS:
            return error("Each meal needs a valid day and meal type")
        key = (day, meal)
        if key in seen:
            return error("A day cannot have the same meal more than once")
        seen.add(key)
        recipe = entry.get("recipe")
        if recipe is None:
            entries.append((day, meal, None))
            continue
        recipe_id, problem = recipe_from_payload(db, recipe, g.user_id)
        if problem:
            return error(problem)
        entries.append((day, meal, recipe_id))

    db.execute("DELETE FROM meal_plan WHERE user_id = ?", (g.user_id,))
    db.executemany(
        "INSERT INTO meal_plan (user_id, day, meal, recipe_id) VALUES (?, ?, ?, ?)",
        [(g.user_id, day, meal, recipe_id) for day, meal, recipe_id in entries if recipe_id],
    )
    db.commit()
    return jsonify({"meals": meal_plan_json(db, g.user_id)})


@bp.delete("/meal-plan")
@login_required
def clear_meal_plan():
    db = get_db()
    db.execute("DELETE FROM meal_plan WHERE user_id = ?", (g.user_id,))
    db.commit()
    return jsonify({"ok": True})
