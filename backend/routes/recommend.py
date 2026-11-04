"""Personalized recipe suggestions ranked by pantry overlap and saved favorites."""
import json
import re

from flask import Blueprint, g, jsonify

from auth_helpers import login_required
from db import get_db

bp = Blueprint("recommend", __name__, url_prefix="/api")


def ingredient_key(value):
    words = re.sub(r"[^a-z0-9 ]", " ", value.lower()).split()
    if words and words[-1].endswith("s") and len(words[-1]) > 3:
        words[-1] = words[-1][:-1]
    return " ".join(words)


@bp.get("/recommendations")
@login_required
def recommendations():
    db = get_db()
    pantry = {
        ingredient_key(row["name"])
        for row in db.execute("SELECT name FROM pantry WHERE user_id = ?", (g.user_id,))
    }
    favorites = {
        row["recipe_id"]
        for row in db.execute("SELECT recipe_id FROM favourites WHERE user_id = ?", (g.user_id,))
    }
    rows = db.execute(
        "SELECT id, name, ingredients, instructions, image, diets, time_min, kcal, "
        "protein, carbs, fat FROM recipes ORDER BY lower(name), id"
    ).fetchall()
    ranked = []
    for row in rows:
        ingredients = json.loads(row["ingredients"])
        matched = sum(ingredient_key(item) in pantry for item in ingredients)
        total = len(ingredients)
        ranked.append({
            "id": row["id"],
            "name": row["name"],
            "ingredients": ingredients,
            "instructions": row["instructions"],
            "image": row["image"],
            "diets": json.loads(row["diets"]),
            "time_min": row["time_min"],
            "kcal": row["kcal"],
            "protein": row["protein"],
            "carbs": row["carbs"],
            "fat": row["fat"],
            "pantry_match": round(matched / total * 100) if total else 0,
            "favorite": row["id"] in favorites,
        })
    ranked.sort(key=lambda recipe: (-recipe["pantry_match"], not recipe["favorite"], recipe["name"].lower()))
    return jsonify({"recommendations": ranked[:6]})
