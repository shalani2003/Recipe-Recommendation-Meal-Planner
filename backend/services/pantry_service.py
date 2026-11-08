"""Pantry rules shared by the pantry routes and the shopping list (J7 "move to pantry")."""
import math
import re
from datetime import date

CATEGORIES = ["Vegetables", "Fruits", "Grains", "Protein", "Dairy", "Spices & sauces", "Other"]
UNITS = ["pcs", "g", "kg", "ml", "l", "cups"]
MAX_QTY = 100000


def parse_expiry(value):
    """'' or None -> None. Otherwise a real YYYY-MM-DD date, or ValueError."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        raise ValueError("Enter the expiry date as YYYY-MM-DD")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValueError("Enter the expiry date as YYYY-MM-DD")


def parse_qty(value):
    if isinstance(value, bool):
        raise ValueError("Enter an amount as a number")
    try:
        qty = float(value)
    except (OverflowError, TypeError, ValueError):
        raise ValueError("Enter an amount as a number")
    if not math.isfinite(qty):
        raise ValueError("Enter an amount as a finite number")
    qty = round(qty, 2)
    if qty <= 0:
        raise ValueError("Amount must be greater than 0")
    if qty > MAX_QTY:
        raise ValueError("Amount is too large")
    return qty


def parse_unit(value):
    unit = str(value or "pcs").strip().lower()
    if unit not in UNITS:
        raise ValueError("Unit must be one of: " + ", ".join(UNITS))
    return unit


def parse_category(value):
    cat = str(value or "Other").strip()
    for known in CATEGORIES:
        if known.lower() == cat.lower():
            return known
    raise ValueError("Category must be one of: " + ", ".join(CATEGORIES))


def sooner(a, b):
    """The earlier of two expiry dates; a missing date never wins."""
    if not a:
        return b
    if not b:
        return a
    return min(a, b)


def sync_legacy_items(db, user_id):
    """Keep pantry_items as a compatibility mirror of the canonical pantry rows."""
    db.execute("DELETE FROM pantry_items WHERE user_id = ?", (user_id,))
    db.execute(
        "INSERT INTO pantry_items (user_id, name, cat, qty, unit, exp) "
        "SELECT user_id, name, category, quantity, unit, expiry_date "
        "FROM pantry WHERE user_id = ?",
        (user_id,),
    )


def add_item(db, user_id, name, cat, qty, unit, exp, manage_transaction=True):
    """Add to the pantry. Same name AND same unit (any letter case) -> quantities are added and
    the earlier expiry date is kept. A different unit stays a separate item, so 1 kg is never
    added to 15 pcs. Returns (row, merged). Set manage_transaction=False when joining a larger
    transaction managed by the caller."""
    if manage_transaction:
        db.execute("BEGIN IMMEDIATE")
    existing = db.execute(
        "SELECT * FROM pantry WHERE user_id = ? AND lower(name) = lower(?) AND unit = ?",
        (user_id, name, unit),
    ).fetchone()
    if existing:
        new_qty = min(round(existing["quantity"] + qty, 2), MAX_QTY)
        db.execute("UPDATE pantry SET quantity = ?, expiry_date = ? WHERE id = ?",
                   (new_qty, sooner(existing["expiry_date"], exp), existing["id"]))
        item_id, merged = existing["id"], True
    else:
        cur = db.execute(
            "INSERT INTO pantry (user_id, name, category, quantity, unit, expiry_date) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, name, cat, qty, unit, exp),
        )
        item_id, merged = cur.lastrowid, False
    sync_legacy_items(db, user_id)
    if manage_transaction:
        db.commit()
    return db.execute("SELECT * FROM pantry WHERE id = ?", (item_id,)).fetchone(), merged


def days_left(exp, today):
    if not exp:
        return None
    expiry_date = date.fromisoformat(parse_expiry(exp))
    return (expiry_date - today).days


def state_for(days):
    if days is None:
        return "none"
    if days < 0:
        return "expired"
    if days == 0:
        return "today"
    if days <= 3:
        return "soon"
    return "ok"
