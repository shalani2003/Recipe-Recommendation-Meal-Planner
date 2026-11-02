"""
Pantry API  (Functional requirement 1: add, edit and remove pantry items)

All routes need a logged-in user and only ever touch that user's own rows.

    GET    /api/pantry              list my items          -> {items, user_id}
    POST   /api/pantry              add an item            -> {item, merged}
    PUT    /api/pantry/<id>         edit (partial update)  -> {item}
    DELETE /api/pantry/<id>         remove one item        -> {ok}
    DELETE /api/pantry              remove everything      -> {ok, deleted}
    POST   /api/pantry/import       bulk add (migration)   -> {imported, merged, skipped}

Item JSON: {id, name, category, quantity, unit, expiry_date}   (expiry_date: "YYYY-MM-DD" or null)
"""
import math
import re
import sqlite3
from datetime import date

from flask import Blueprint, jsonify, request

from auth_utils import current_user_id, login_required
from database import get_db

pantry_bp = Blueprint("pantry", __name__)

CATEGORIES = ["Vegetables", "Fruits", "Grains", "Protein", "Dairy", "Spices & sauces", "Other"]
UNITS = ["pcs", "g", "kg", "ml", "l", "cups"]
# Category names used by the shopping page, mapped to pantry categories.
CATEGORY_ALIASES = {"produce": "Vegetables", "pantry": "Grains", "spices & oils": "Spices & sauces"}

MAX_NAME_LENGTH = 80
MAX_QUANTITY = 100000
MAX_IMPORT_ITEMS = 500
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(Exception):
    """The request contained a bad value (HTTP 400)."""


class ConflictError(Exception):
    """The request clashes with an existing item (HTTP 409)."""


# -------------------------------------------------------------- validation
def parse_name(value):
    name = " ".join(str(value or "").split())
    if not name:
        raise ValidationError("Enter an ingredient name")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"Name must be {MAX_NAME_LENGTH} characters or fewer")
    return name


def parse_category(value):
    if value is None or str(value).strip() == "":
        return "Other"
    text = str(value).strip().lower()
    for category in CATEGORIES:
        if category.lower() == text:
            return category
    if text in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[text]
    raise ValidationError("Choose a valid category")


def parse_quantity(value):
    if isinstance(value, bool):
        raise ValidationError("Quantity must be a number")
    try:
        quantity = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Quantity must be a number")
    if not math.isfinite(quantity) or quantity <= 0:
        raise ValidationError("Quantity must be greater than 0")
    if quantity > MAX_QUANTITY:
        raise ValidationError(f"Quantity must be {MAX_QUANTITY:,} or less")
    return round(quantity, 3)


def parse_unit(value):
    if value is None or str(value).strip() == "":
        return "pcs"
    text = str(value).strip().lower()
    if text not in UNITS:
        raise ValidationError("Choose a valid unit")
    return text


def parse_expiry(value):
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        if not DATE_RE.match(text):
            raise ValueError
        date.fromisoformat(text)
    except ValueError:
        raise ValidationError("Expiry date must look like 2026-12-31")
    return text


def parse_item(data, lenient=False):
    """
    Validate a complete item. With lenient=True (used for the import) a bad
    category/unit/expiry falls back to a default instead of rejecting the item.
    """
    item = {
        "name": parse_name(data.get("name")),
        "quantity": parse_quantity(data.get("quantity", 1)),
    }
    for key, parser, default in (
        ("category", parse_category, "Other"),
        ("unit", parse_unit, "pcs"),
        ("expiry_date", parse_expiry, None),
    ):
        try:
            item[key] = parser(data.get(key))
        except ValidationError:
            if not lenient:
                raise
            item[key] = default
    return item


def parse_changes(data):
    """Validate only the fields that were sent (partial update)."""
    parsers = {
        "name": parse_name,
        "category": parse_category,
        "quantity": parse_quantity,
        "unit": parse_unit,
        "expiry_date": parse_expiry,
    }
    changes = {key: parser(data[key]) for key, parser in parsers.items() if key in data}
    if not changes:
        raise ValidationError("Nothing to update")
    return changes


# ----------------------------------------------------------------- helpers
def error(message, status=400):
    return jsonify({"error": message}), status


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def serialize(row):
    quantity = row["quantity"]
    if float(quantity).is_integer():
        quantity = int(quantity)
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "quantity": quantity,
        "unit": row["unit"],
        "expiry_date": row["expiry_date"],
    }


def get_item(db, user_id, item_id):
    return db.execute(
        "SELECT * FROM pantry_items WHERE id = ? AND user_id = ?", (item_id, user_id)
    ).fetchone()


def earliest_date(first, second):
    """When two stocks of an item are merged, remember the date to use first."""
    if first and second:
        return min(first, second)
    return first or second


def add_or_merge(db, user_id, item):
    """
    Insert the item, or - if the user already has an ingredient with the same
    name - add the quantity to it. Returns (row, merged).
    """
    existing = db.execute(
        "SELECT * FROM pantry_items WHERE user_id = ? AND name = ? COLLATE NOCASE",
        (user_id, item["name"]),
    ).fetchone()

    if existing is None:
        cur = db.execute(
            """INSERT INTO pantry_items (user_id, name, category, quantity, unit, expiry_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, item["name"], item["category"], item["quantity"], item["unit"], item["expiry_date"]),
        )
        return get_item(db, user_id, cur.lastrowid), False

    if existing["unit"] != item["unit"]:
        raise ConflictError(
            f'"{existing["name"]}" is already in your pantry in {existing["unit"]}. '
            "Edit that item instead."
        )
    db.execute(
        """UPDATE pantry_items
           SET quantity = ?, expiry_date = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ? AND user_id = ?""",
        (
            min(existing["quantity"] + item["quantity"], MAX_QUANTITY),
            earliest_date(existing["expiry_date"], item["expiry_date"]),
            existing["id"],
            user_id,
        ),
    )
    return get_item(db, user_id, existing["id"]), True


# ------------------------------------------------------------------ routes
@pantry_bp.get("/api/pantry")
@login_required
def list_items():
    uid = current_user_id()
    rows = get_db().execute(
        "SELECT * FROM pantry_items WHERE user_id = ? ORDER BY name COLLATE NOCASE", (uid,)
    ).fetchall()
    return jsonify({"items": [serialize(r) for r in rows], "user_id": uid})


@pantry_bp.post("/api/pantry")
@login_required
def create_item():
    db = get_db()
    try:
        item = parse_item(body())
        row, merged = add_or_merge(db, current_user_id(), item)
    except ValidationError as exc:
        return error(str(exc))
    except ConflictError as exc:
        return error(str(exc), 409)
    db.commit()
    return jsonify({"item": serialize(row), "merged": merged}), (200 if merged else 201)


@pantry_bp.route("/api/pantry/<int:item_id>", methods=["PUT", "PATCH"])
@login_required
def update_item(item_id):
    db = get_db()
    uid = current_user_id()
    if get_item(db, uid, item_id) is None:
        return error("Pantry item not found", 404)
    try:
        changes = parse_changes(body())
    except ValidationError as exc:
        return error(str(exc))

    # Column names come from the fixed whitelist in parse_changes, never from the client.
    assignments = ", ".join(f"{column} = ?" for column in changes)
    try:
        db.execute(
            f"UPDATE pantry_items SET {assignments}, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ?",
            (*changes.values(), item_id, uid),
        )
    except sqlite3.IntegrityError:
        db.rollback()
        return error("Another pantry item already has that name", 409)
    db.commit()
    return jsonify({"item": serialize(get_item(db, uid, item_id))})


@pantry_bp.delete("/api/pantry/<int:item_id>")
@login_required
def delete_item(item_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM pantry_items WHERE id = ? AND user_id = ?", (item_id, current_user_id())
    )
    db.commit()
    if cur.rowcount == 0:
        return error("Pantry item not found", 404)
    return jsonify({"ok": True})


@pantry_bp.delete("/api/pantry")
@login_required
def clear_items():
    db = get_db()
    cur = db.execute("DELETE FROM pantry_items WHERE user_id = ?", (current_user_id(),))
    db.commit()
    return jsonify({"ok": True, "deleted": cur.rowcount})


@pantry_bp.post("/api/pantry/import")
@login_required
def import_items():
    """Bulk add. Used once to move pantry items saved in the browser into the database."""
    items = body().get("items")
    if not isinstance(items, list):
        return error("Send a list called 'items'")
    if len(items) > MAX_IMPORT_ITEMS:
        return error(f"You can import at most {MAX_IMPORT_ITEMS} items at once")

    db = get_db()
    uid = current_user_id()
    imported = merged = skipped = 0
    for raw in items:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        try:
            _row, was_merged = add_or_merge(db, uid, parse_item(raw, lenient=True))
        except (ValidationError, ConflictError):
            skipped += 1
            continue
        if was_merged:
            merged += 1
        else:
            imported += 1
    db.commit()
    return jsonify({"imported": imported, "merged": merged, "skipped": skipped})
