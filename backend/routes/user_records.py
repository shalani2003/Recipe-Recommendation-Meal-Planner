"""Shopping, hydration, and weight-history APIs."""
import math
from datetime import date

from flask import Blueprint, g, jsonify, request

from auth_helpers import body, clean_text, error, login_required
from db import get_db

bp = Blueprint("user_records", __name__, url_prefix="/api")
MAX_SHOPPING_ITEMS = 500
MAX_AMOUNT = 100000
MAX_GLASSES = 30


def parse_day(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def shopping_items(db, user_id):
    rows = db.execute(
        "SELECT id, name, qty, unit, cat, bought FROM shopping_items "
        "WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "quantity": row["qty"],
            "unit": row["unit"],
            "category": row["cat"],
            "done": bool(row["bought"]),
            "bought": bool(row["bought"]),
        }
        for row in rows
    ]


@bp.get("/shopping")
@login_required
def get_shopping():
    return jsonify({"items": shopping_items(get_db(), g.user_id)})


@bp.put("/shopping")
@login_required
def replace_shopping():
    data = body()
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return error("items must be a list")
    if len(data["items"]) > MAX_SHOPPING_ITEMS:
        return error("A shopping list can contain at most 500 items")

    cleaned = []
    for item in data["items"]:
        if not isinstance(item, dict):
            return error("Each shopping item must be an object")
        name, problem = clean_text(item.get("name"), "an item name", 1, 120)
        if problem:
            return error(problem)
        done = item.get("done", item.get("bought", False))
        if not isinstance(done, bool):
            return error("Shopping item done must be true or false")
        quantity = item.get("quantity", item.get("qty"))
        if quantity in ("", None):
            quantity = None
        elif isinstance(quantity, bool):
            return error("Shopping quantity must be a positive number")
        else:
            try:
                quantity = float(quantity)
            except (OverflowError, TypeError, ValueError):
                return error("Shopping quantity must be a positive number")
            if not math.isfinite(quantity) or quantity <= 0 or quantity > MAX_AMOUNT:
                return error("Shopping quantity must be greater than 0 and at most 100000")

        unit = item.get("unit")
        category = item.get("category", item.get("cat"))
        if unit is not None and (not isinstance(unit, str) or len(unit) > 30):
            return error("Shopping unit must be 30 characters or fewer")
        if category is not None and (not isinstance(category, str) or len(category) > 60):
            return error("Shopping category must be 60 characters or fewer")
        cleaned.append((g.user_id, name, quantity, unit, category, int(done)))

    db = get_db()
    db.execute("DELETE FROM shopping_items WHERE user_id = ?", (g.user_id,))
    db.executemany(
        "INSERT INTO shopping_items (user_id, name, qty, unit, cat, bought) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        cleaned,
    )
    db.commit()
    return jsonify({"items": shopping_items(db, g.user_id)})


@bp.delete("/shopping")
@login_required
def clear_shopping():
    db = get_db()
    cursor = db.execute("DELETE FROM shopping_items WHERE user_id = ?", (g.user_id,))
    db.commit()
    return jsonify({"ok": True, "removed": cursor.rowcount})


@bp.get("/water")
@login_required
def get_water():
    raw_day = request.args.get("day", date.today().isoformat())
    day = parse_day(raw_day)
    if day is None:
        return error("day must be a valid YYYY-MM-DD date")
    row = get_db().execute(
        "SELECT glasses FROM water WHERE user_id = ? AND day = ?", (g.user_id, day)
    ).fetchone()
    return jsonify({"day": day, "glasses": row["glasses"] if row else 0})


@bp.put("/water")
@login_required
def save_water():
    data = body()
    if not isinstance(data, dict):
        return error("Water tracking must be a JSON object")
    day = parse_day(data.get("day", date.today().isoformat()))
    if day is None:
        return error("day must be a valid YYYY-MM-DD date")
    glasses = data.get("glasses")
    if isinstance(glasses, bool) or not isinstance(glasses, int) or not 0 <= glasses <= MAX_GLASSES:
        return error("glasses must be a whole number from 0 to 30")
    db = get_db()
    db.execute(
        "INSERT INTO water (user_id, day, glasses) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, day) DO UPDATE SET glasses = excluded.glasses",
        (g.user_id, day, glasses),
    )
    db.commit()
    return jsonify({"day": day, "glasses": glasses})


@bp.get("/weight-log")
@login_required
def get_weight_log():
    rows = get_db().execute(
        "SELECT id, weight_kg, logged_on FROM weight_log "
        "WHERE user_id = ? ORDER BY logged_on DESC, id DESC LIMIT 100",
        (g.user_id,),
    ).fetchall()
    return jsonify({
        "entries": [
            {"id": row["id"], "weight_kg": row["weight_kg"], "logged_on": row["logged_on"]}
            for row in rows
        ]
    })


@bp.post("/weight-log")
@login_required
def add_weight_log():
    data = body()
    if not isinstance(data, dict):
        return error("Weight entry must be a JSON object")
    weight = data.get("weight_kg")
    if isinstance(weight, bool):
        return error("weight_kg must be a number from 25 to 250")
    try:
        weight = float(weight)
    except (OverflowError, TypeError, ValueError):
        return error("weight_kg must be a number from 25 to 250")
    if not math.isfinite(weight) or not 25 <= weight <= 250:
        return error("weight_kg must be a number from 25 to 250")
    logged_on = parse_day(data.get("logged_on", date.today().isoformat()))
    if logged_on is None:
        return error("logged_on must be a valid YYYY-MM-DD date")
    db = get_db()
    cursor = db.execute(
        "INSERT INTO weight_log (user_id, weight_kg, logged_on) VALUES (?, ?, ?)",
        (g.user_id, weight, logged_on),
    )
    db.commit()
    row = db.execute(
        "SELECT id, weight_kg, logged_on FROM weight_log WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify({"entry": {
        "id": row["id"], "weight_kg": row["weight_kg"], "logged_on": row["logged_on"]
    }}), 201
