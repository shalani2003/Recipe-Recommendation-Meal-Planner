"""Persist user favorites, ratings, and meal plans."""
import json
import re

from flask import Blueprint, g, jsonify

from auth_helpers import body, error, login_required
from db import get_db

bp = Blueprint("user_food", __name__, url_prefix="/api")
DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
MEALS = {"Breakfast", "Lunch", "Dinner"}
BAD_RECIPE_NAME = re.compile(r"[<>\x00-\x1f]")


def recipe_from_payload(db, data, create=True):
    if not isinstance(data, dict):
        return None, "A recipe object is required"
    name = data.get("name")
    if not isinstance(name, str):
        return None, "Recipe name must be text"
    name = " ".join(name.split())
    if not name or len(name) > 80 or BAD_RECIPE_NAME.search(name):
        return None, "Recipe name must be 1 to 80 characters of plain text"
    row = db.execute(
        "SELECT id FROM recipes WHERE lower(name) = lower(?) ORDER BY id LIMIT 1", (name,)
    ).fetchone()
    if row:
        return row["id"], None
    if not create:
        return None, None

    ingredients = data.get("ingredients", data.get("ing", []))
    if not isinstance(ingredients, list) or any(
        not isinstance(item, str) or len(item) > 100 for item in ingredients
    ):
        return None, "Recipe ingredients must be a list of text values"
    cleaned = [" ".join(item.split()) for item in ingredients]
    if len(cleaned) > 100:
        return None, "A recipe can have up to 100 ingredients"
    cursor = db.execute(
        "INSERT INTO recipes (name, ingredients, instructions) VALUES (?, ?, ?)",
        (name, json.dumps(cleaned), ""),
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


@bp.get("/favorites")
@bp.get("/favourites")
@login_required
def list_favorites():
    rows = get_db().execute(
        "SELECT r.name FROM favourites AS f JOIN recipes AS r ON r.id = f.recipe_id "
        "WHERE f.user_id = ? ORDER BY lower(r.name)",
        (g.user_id,),
    ).fetchall()
    return jsonify({"favorites": [row["name"] for row in rows]})


@bp.post("/favorites")
@bp.post("/favourites")
@login_required
def add_favorite():
    db = get_db()
    recipe_id, problem = recipe_from_payload(db, body())
    if problem:
        return error(problem)
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
    recipe_id, problem = recipe_from_payload(db, body(), create=False)
    if problem:
        return error(problem)
    if recipe_id is not None:
        db.execute(
            "DELETE FROM favourites WHERE user_id = ? AND recipe_id = ?",
            (g.user_id, recipe_id),
        )
        db.commit()
    return jsonify({"ok": True})


@bp.get("/ratings")
@login_required
def list_ratings():
    rows = get_db().execute(
        "SELECT r.name, rt.stars FROM ratings AS rt JOIN recipes AS r ON r.id = rt.recipe_id "
        "WHERE rt.user_id = ?",
        (g.user_id,),
    ).fetchall()
    return jsonify({"ratings": {row["name"]: row["stars"] for row in rows}})


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
        recipe_id, problem = recipe_from_payload(db, data, create=False)
        if problem:
            return error(problem)
        if recipe_id is not None:
            db.execute(
                "DELETE FROM ratings WHERE user_id = ? AND recipe_id = ?",
                (g.user_id, recipe_id),
            )
            db.commit()
        return jsonify({"ok": True})

    recipe_id, problem = recipe_from_payload(db, data)
    if problem:
        return error(problem)
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
        recipe_id, problem = recipe_from_payload(db, recipe)
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
