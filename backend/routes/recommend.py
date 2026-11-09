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


DIET_TERMS = {
    "Vegetarian": ("chicken", "turkey", "beef", "pork", "lamb", "meat", "fish", "salmon", "tuna", "trout", "cod", "anchovy", "sardine", "mackerel", "shrimp", "prawn", "crab", "lobster", "gelatin", "meat broth", "chicken broth"),
    "Vegan": ("chicken", "turkey", "beef", "pork", "lamb", "meat", "fish", "salmon", "tuna", "trout", "cod", "anchovy", "sardine", "mackerel", "shrimp", "prawn", "crab", "lobster", "gelatin", "egg", "milk", "yogurt", "cheese", "butter", "cream", "honey", "whey", "casein"),
    "Gluten-free": ("wheat", "flour", "bread", "pasta", "barley", "rye", "semolina", "couscous", "bulgur", "malt", "gluten"),
    "Dairy-free": ("milk", "yogurt", "cheese", "butter", "cream", "dairy", "whey", "casein"),
    "Nut-free": ("peanut", "almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut", "nut"),
    "Halal": ("pork", "ham", "bacon", "lard", "alcohol", "wine", "beer"),
    "Low sugar": ("sugar", "honey", "syrup"),
}

ALLERGY_TERMS = {
    "peanut": ("peanut",),
    "tree nut": ("almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut", "nut"),
    "milk": ("milk", "yogurt", "cheese", "butter", "cream", "dairy", "whey", "casein"),
    "dairy": ("milk", "yogurt", "cheese", "butter", "cream", "dairy", "whey", "casein"),
    "lactose": ("milk", "yogurt", "cheese", "butter", "cream", "dairy"),
    "egg": ("egg",),
    "soy": ("soy", "soya", "tofu"),
    "wheat": ("wheat", "flour", "bread", "pasta", "barley", "rye", "semolina", "couscous", "bulgur", "malt", "gluten"),
    "gluten": ("wheat", "flour", "bread", "pasta", "barley", "rye", "semolina", "couscous", "bulgur", "malt", "gluten"),
    "fish": ("fish", "salmon", "tuna", "trout", "cod", "anchovy", "sardine", "mackerel"),
    "seafood": ("fish", "salmon", "tuna", "trout", "cod", "anchovy", "sardine", "mackerel", "shrimp", "prawn", "crab", "lobster", "shellfish"),
    "shellfish": ("shrimp", "prawn", "crab", "lobster", "shellfish", "mussel", "clam", "oyster"),
    "sesame": ("sesame", "tahini"),
}


def decode_list(value):
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def contains_term(ingredient, term):
    text = ingredient_key(str(ingredient))
    term = ingredient_key(term)
    if term == "milk" and re.search(
        r"\b(?:almond|cashew|coconut|flax|hemp|oat|pea|rice|soy|soya) milk\b", text
    ):
        return False
    return bool(text and term and re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text))


def recipe_conflicts(ingredients, terms):
    return any(contains_term(ingredient, term) for ingredient in ingredients for term in terms)


def allergy_terms(allergy):
    key = ingredient_key(allergy)
    if "diabet" in key or "low sugar" in key:
        return ("sugar", "honey", "syrup")
    for category, terms in ALLERGY_TERMS.items():
        if category in key:
            return terms
    return (key,)


@bp.get("/recommendations")
@login_required
def recommendations():
    db = get_db()
    dietary = db.execute(
        "SELECT diets, allergies FROM dietary WHERE user_id = ?", (g.user_id,)
    ).fetchone()
    diets = decode_list(dietary["diets"]) if dietary else []
    allergies = decode_list(dietary["allergies"]) if dietary else []

    # Include profile data for accounts created before dietary settings were added.
    profile = db.execute(
        "SELECT allergies, health_notes FROM profiles WHERE user_id = ?", (g.user_id,)
    ).fetchone()
    if profile:
        allergies.extend(decode_list(profile["allergies"]))
        health_notes = str(profile["health_notes"] or "")
        allergies.extend(part.strip() for part in health_notes.split(",") if part.strip())
    allergies = list(dict.fromkeys(str(value).strip().lower() for value in allergies if str(value).strip()))

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
        if any(diet in DIET_TERMS and recipe_conflicts(ingredients, DIET_TERMS[diet]) for diet in diets):
            continue
        if any(recipe_conflicts(ingredients, allergy_terms(allergy)) for allergy in allergies):
            continue
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
