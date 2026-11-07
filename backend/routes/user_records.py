"""Shopping, hydration, and weight-history APIs."""
import math
from datetime import date

from flask import Blueprint, g, jsonify, request

from auth_helpers import body, clean_text, error, login_required
from db import get_db
from services import pantry_service as ps

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
        "SELECT id, name, qty, unit, cat, bought, expiry_date, source, "
        "manual_quantity_base FROM shopping_items "
        "WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "item_name": row["name"],
            "quantity": row["qty"],
            "qty": row["qty"],
            "unit": row["unit"],
            "category": row["cat"],
            "expiry_date": row["expiry_date"],
            "done": bool(row["bought"]),
            "bought": bool(row["bought"]),
            "is_bought": bool(row["bought"]),
            "source": row["source"],
            "manualQuantityBase": row["manual_quantity_base"],
        }
        for row in rows
    ]


def shopping_item(data):
    if not isinstance(data, dict):
        return None, "Each shopping item must be an object"
    name, problem = clean_text(
        data.get("name", data.get("item_name")), "an item name", 1, 120, allow_markup=True
    )
    if problem:
        return None, problem
    done = data.get("done", data.get("bought", data.get("is_bought", False)))
    if not isinstance(done, bool):
        return None, "Shopping item done must be true or false"
    quantity = data.get("quantity", data.get("qty"))
    if quantity in ("", None):
        quantity = None
    elif isinstance(quantity, bool):
        return None, "Shopping quantity must be a positive number"
    else:
        try:
            quantity = float(quantity)
        except (OverflowError, TypeError, ValueError):
            return None, "Shopping quantity must be a positive number"
        if not math.isfinite(quantity) or quantity <= 0 or quantity > MAX_AMOUNT:
            return None, "Shopping quantity must be greater than 0 and at most 100000"

    unit = data.get("unit")
    category = data.get("category", data.get("cat"))
    if unit is not None and (not isinstance(unit, str) or len(unit) > 30):
        return None, "Shopping unit must be 30 characters or fewer"
    if category is not None and (not isinstance(category, str) or len(category) > 60):
        return None, "Shopping category must be 60 characters or fewer"
    expiry_date = data.get("expiry_date")
    if expiry_date in ("", None):
        expiry_date = None
    elif not isinstance(expiry_date, str) or parse_day(expiry_date) is None:
        return None, "expiry_date must be a valid YYYY-MM-DD date"
    source = data.get("source", "manual")
    if source not in ("manual", "meal-plan"):
        return None, "Shopping item source must be manual or meal-plan"
    manual_quantity_base = data.get("manualQuantityBase", data.get("manual_quantity_base"))
    if manual_quantity_base in ("", None):
        manual_quantity_base = None
    elif isinstance(manual_quantity_base, bool):
        return None, "manualQuantityBase must be a non-negative number"
    else:
        try:
            manual_quantity_base = float(manual_quantity_base)
        except (OverflowError, TypeError, ValueError):
            return None, "manualQuantityBase must be a non-negative number"
        if not math.isfinite(manual_quantity_base) or not 0 <= manual_quantity_base <= MAX_AMOUNT:
            return None, "manualQuantityBase must be a non-negative number"

    return (
        name, quantity, unit, category, int(done), expiry_date, source,
        manual_quantity_base,
    ), None


def shopping_item_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "item_name": row["name"],
        "quantity": row["qty"],
        "qty": row["qty"],
        "unit": row["unit"],
        "category": row["cat"],
        "expiry_date": row["expiry_date"],
        "done": bool(row["bought"]),
        "bought": bool(row["bought"]),
        "is_bought": bool(row["bought"]),
        "source": row["source"],
        "manualQuantityBase": row["manual_quantity_base"],
    }


@bp.get("/shopping")
@login_required
def get_shopping():
    return jsonify({"items": shopping_items(get_db(), g.user_id)})


@bp.post("/shopping")
@login_required
def add_shopping_item():
    item, problem = shopping_item(body())
    if problem:
        return error(problem)
    name, quantity, unit, category, done, expiry_date, source, manual_base = item
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    existing = db.execute(
        "SELECT * FROM shopping_items WHERE user_id = ? AND lower(trim(name)) = lower(?) "
        "AND lower(COALESCE(unit, '')) = lower(COALESCE(?, '')) "
        "AND COALESCE(expiry_date, '') = COALESCE(?, '') ORDER BY id LIMIT 1",
        (g.user_id, name, unit, expiry_date),
    ).fetchone()
    merged = existing is not None
    if existing:
        requested_source = source
        added_quantity = quantity
        current_quantity = existing["qty"]
        if current_quantity is not None and quantity is not None:
            quantity = current_quantity + quantity
            if quantity > MAX_AMOUNT:
                db.rollback()
                return error("Combined shopping quantity cannot exceed 100000")
        elif current_quantity is not None:
            quantity = current_quantity
        source = "meal-plan" if existing["source"] == "meal-plan" else source
        if existing["source"] == "meal-plan":
            if requested_source == "manual":
                manual_base = (existing["manual_quantity_base"] or 0) + (added_quantity or 0)
            elif manual_base is None:
                manual_base = existing["manual_quantity_base"]
        elif manual_base is None:
            manual_base = existing["manual_quantity_base"]
        db.execute(
            "UPDATE shopping_items SET qty = ?, cat = COALESCE(?, cat), "
            "bought = ?, source = ?, manual_quantity_base = ? WHERE id = ? AND user_id = ?",
            (quantity, category, int(bool(done or existing["bought"])), source,
             manual_base, existing["id"], g.user_id),
        )
        item_id = existing["id"]
    else:
        count = db.execute(
            "SELECT COUNT(*) FROM shopping_items WHERE user_id = ?", (g.user_id,)
        ).fetchone()[0]
        if count >= MAX_SHOPPING_ITEMS:
            db.rollback()
            return error("A shopping list can contain at most 500 items")
        cursor = db.execute(
            "INSERT INTO shopping_items "
            "(user_id, name, qty, unit, cat, bought, expiry_date, source, manual_quantity_base) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (g.user_id, name, quantity, unit, category, done, expiry_date, source, manual_base),
        )
        item_id = cursor.lastrowid
    db.commit()
    row = db.execute(
        "SELECT * FROM shopping_items WHERE id = ? AND user_id = ?", (item_id, g.user_id)
    ).fetchone()
    return jsonify({"item": shopping_item_json(row), "merged": merged}), (200 if merged else 201)


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
        parsed, problem = shopping_item(item)
        if problem:
            return error(problem)
        name, quantity, unit, category, done, expiry_date, source, manual_base = parsed
        cleaned.append(
            (g.user_id, name, quantity, unit, category, done, expiry_date, source, manual_base)
        )

    db = get_db()
    db.execute("DELETE FROM shopping_items WHERE user_id = ?", (g.user_id,))
    db.executemany(
        "INSERT INTO shopping_items "
        "(user_id, name, qty, unit, cat, bought, expiry_date, source, manual_quantity_base) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        cleaned,
    )
    db.commit()
    return jsonify({"items": shopping_items(db, g.user_id)})


@bp.patch("/shopping/<int:item_id>")
@login_required
def update_shopping_item(item_id):
    data = body()
    if not isinstance(data, dict):
        return error("Shopping item update must be a JSON object")
    bought_key = next(
        (key for key in ("is_bought", "bought", "done") if key in data), None
    )
    if bought_key is None or not isinstance(data[bought_key], bool):
        return error("Send is_bought as true or false")
    db = get_db()
    cursor = db.execute(
        "UPDATE shopping_items SET bought = ? WHERE id = ? AND user_id = ?",
        (int(data[bought_key]), item_id, g.user_id),
    )
    if cursor.rowcount == 0:
        return error("Item not found", 404)
    db.commit()
    row = db.execute(
        "SELECT * FROM shopping_items WHERE id = ? AND user_id = ?", (item_id, g.user_id)
    ).fetchone()
    return jsonify({"item": shopping_item_json(row)})


@bp.delete("/shopping/<int:item_id>")
@login_required
def delete_shopping_item(item_id):
    db = get_db()
    cursor = db.execute(
        "DELETE FROM shopping_items WHERE id = ? AND user_id = ?", (item_id, g.user_id)
    )
    if cursor.rowcount == 0:
        return error("Item not found", 404)
    db.commit()
    return jsonify({"ok": True, "removed": 1})


@bp.post("/shopping/<int:item_id>/move-to-pantry")
@login_required
def move_shopping_item_to_pantry(item_id):
    data = body()
    if not isinstance(data, dict):
        return error("Pantry item must be a JSON object")

    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    shopping_item = db.execute(
        "SELECT * FROM shopping_items WHERE id = ? AND user_id = ?",
        (item_id, g.user_id),
    ).fetchone()
    if shopping_item is None:
        db.rollback()
        return error("Shopping item was not found or has already been moved", 404)
    if not shopping_item["bought"]:
        db.rollback()
        return error("Mark the shopping item as bought before moving it to the Pantry")

    name, problem = clean_text(
        shopping_item["name"], "an item name", 1, 60, allow_markup=True
    )
    if problem:
        db.rollback()
        return error(problem)
    try:
        quantity = ps.parse_qty(data.get("quantity", data.get("qty")))
        unit = ps.parse_unit(data.get("unit"))
        category = ps.parse_category(data.get("category") or "Other")
        expiry = ps.parse_expiry(
            data.get("expiry_date") or shopping_item["expiry_date"]
        )
    except ValueError as exc:
        db.rollback()
        return error(str(exc))

    _, merged = ps.add_item(
        db, g.user_id, name, category, quantity, unit, expiry,
        manage_transaction=False,
    )
    deleted = db.execute(
        "DELETE FROM shopping_items WHERE id = ? AND user_id = ?",
        (item_id, g.user_id),
    )
    if deleted.rowcount != 1:
        db.rollback()
        return error("Shopping item could not be moved", 409)
    db.commit()
    return jsonify({"ok": True, "merged": merged, "removed": 1})


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
