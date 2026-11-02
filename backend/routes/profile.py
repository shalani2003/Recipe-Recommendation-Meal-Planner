"""Profile details and health measurements."""
import json
import math

from flask import Blueprint, g, jsonify

from auth_helpers import BAD_TEXT_RE, body, clean_text, error, login_required
from db import get_db

bp = Blueprint("profile", __name__, url_prefix="/api")

NUMBER_FIELDS = {
    "age": (1, 120, True),
    "height": (100, 230, False),
    "weight": (25, 250, False),
    "calorie_goal": (1000, 4000, True),
    "target_weight": (25, 250, False),
}


def parse_number(value, field, limits):
    minimum, maximum, integer = limits
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, "%s must be a number" % field.replace("_", " ")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None, "%s must be a number" % field.replace("_", " ")
    if not math.isfinite(number):
        return None, "%s must be a finite number" % field.replace("_", " ")
    if integer and not number.is_integer():
        return None, "%s must be a whole number" % field.replace("_", " ")
    if number < minimum or number > maximum:
        return None, "%s must be between %s and %s" % (
            field.replace("_", " "), minimum, maximum)
    return int(number) if integer else number, None


def parse_allergies(value):
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        return None, "allergies must be text or a list of text values"
    clean = []
    for allergy in values:
        if not isinstance(allergy, str):
            return None, "Each allergy must be text"
        text = " ".join(allergy.split()).lower()
        if not text:
            continue
        if len(text) > 40 or BAD_TEXT_RE.search(text):
            return None, "Each allergy must be 40 characters or fewer and plain text"
        if text not in clean:
            clean.append(text)
    if len(clean) > 20:
        return None, "You can list up to 20 allergies"
    return clean, None


def read_profile(db, user_id):
    row = db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    user = db.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        dietary = db.execute("SELECT allergies FROM dietary WHERE user_id = ?", (user_id,)).fetchone()
        return {
            "name": user["name"],
            "age": None,
            "height": None,
            "weight": None,
            "allergies": json.loads(dietary["allergies"]) if dietary else [],
            "health_notes": "",
            "calorie_goal": None,
            "target_weight": None,
        }
    return {
        "name": row["name"] or user["name"],
        "age": row["age"],
        "height": row["height"],
        "weight": row["weight"],
        "allergies": json.loads(row["allergies"]),
        "health_notes": row["health_notes"],
        "calorie_goal": row["calorie_goal"],
        "target_weight": row["target_weight"],
    }


@bp.get("/profile")
@login_required
def get_profile():
    return jsonify(read_profile(get_db(), g.user_id))


@bp.put("/profile")
@login_required
def put_profile():
    data = body()
    if not isinstance(data, dict):
        return error("The profile must be a JSON object")

    db = get_db()
    profile = read_profile(db, g.user_id)

    if "name" in data:
        name, problem = clean_text(data["name"], "your name", 2, 60)
        if problem:
            return error(problem)
        profile["name"] = name

    for field, limits in NUMBER_FIELDS.items():
        if field in data:
            parsed, problem = parse_number(data[field], field, limits)
            if problem:
                return error(problem)
            profile[field] = parsed

    if "allergies" in data:
        allergies, problem = parse_allergies(data["allergies"])
        if problem:
            return error(problem)
        profile["allergies"] = allergies

    notes_key = "health_notes" if "health_notes" in data else "infections"
    if notes_key in data:
        notes, problem = clean_text(data[notes_key], "health notes", 0, 500)
        if problem:
            return error(problem)
        profile["health_notes"] = notes

    db.execute(
        "INSERT INTO profiles "
        "(user_id, name, age, height, weight, allergies, health_notes, calorie_goal, target_weight) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, age=excluded.age, "
        "height=excluded.height, weight=excluded.weight, allergies=excluded.allergies, "
        "health_notes=excluded.health_notes, calorie_goal=excluded.calorie_goal, "
        "target_weight=excluded.target_weight",
        (
            g.user_id,
            profile["name"],
            profile["age"],
            profile["height"],
            profile["weight"],
            json.dumps(profile["allergies"]),
            profile["health_notes"],
            profile["calorie_goal"],
            profile["target_weight"],
        ),
    )
    db.execute("UPDATE users SET name = ? WHERE id = ?", (profile["name"], g.user_id))
    db.execute(
        "INSERT INTO health (user_id, height_cm, weight_kg, target_kg) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET height_cm=excluded.height_cm, "
        "weight_kg=excluded.weight_kg, target_kg=excluded.target_kg",
        (g.user_id, profile["height"], profile["weight"], profile["target_weight"]),
    )
    db.execute(
        "INSERT INTO dietary (user_id, allergies) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET allergies = excluded.allergies",
        (g.user_id, json.dumps(profile["allergies"])),
    )
    db.commit()
    return jsonify(profile)
