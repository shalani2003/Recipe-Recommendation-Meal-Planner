"""Pantry API (task P3). Quantities can be decimals; an item at 0 is removed."""
from datetime import date

from flask import Blueprint, g, jsonify, request

from auth_helpers import body, clean_text, error, login_required
from db import get_db
from services import pantry_service as ps

bp = Blueprint("pantry", __name__, url_prefix="/api")


def item_json(row, today):
    expiry_date = row["expiry_date"]
    quantity = row["quantity"]
    category = row["category"]
    d = ps.days_left(expiry_date, today)
    return {
        "id": row["id"],
        "name": row["name"],
        "category": category,
        "quantity": quantity,
        "unit": row["unit"],
        "expiry_date": expiry_date,
        "cat": category,
        "qty": quantity,
        "exp": expiry_date,
        "days_left": d,
        "state": ps.state_for(d),
    }


def client_today():
    """The browser sends its own local date (?today=YYYY-MM-DD) so expiry labels are right in
    every time zone. Without it the server's date is used."""
    raw = request.args.get("today")
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return date.today()


def own_item(item_id):
    return get_db().execute(
        "SELECT * FROM pantry WHERE id = ? AND user_id = ?", (item_id, g.user_id)).fetchone()


@bp.get("/pantry")
@login_required
def list_pantry():
    today = client_today()
    rows = get_db().execute(
        "SELECT * FROM pantry WHERE user_id = ? ORDER BY category, lower(name)", (g.user_id,)).fetchall()
    items = [item_json(r, today) for r in rows]
    summary = {"items": len(items),
               "use_soon": sum(1 for i in items if i["state"] in ("today", "soon")),
               "expired": sum(1 for i in items if i["state"] == "expired")}
    return jsonify({"items": items, "summary": summary})


@bp.post("/pantry")
@login_required
def add_pantry():
    data = body()
    if not isinstance(data, dict):
        return error("Pantry item must be a JSON object")
    name, problem = clean_text(data.get("name"), "an item name", 1, 60)
    if problem:
        return error(problem)
    try:
        qty = ps.parse_qty(data.get("quantity", data.get("qty", 1)))
        unit = ps.parse_unit(data.get("unit"))
        cat = ps.parse_category(data.get("category", data.get("cat")))
        exp = ps.parse_expiry(data.get("expiry_date", data.get("exp")))
    except ValueError as e:
        return error(str(e))
    row, merged = ps.add_item(get_db(), g.user_id, name, cat, qty, unit, exp)
    return jsonify({"item": item_json(row, client_today()), "merged": merged}), (200 if merged else 201)


@bp.get("/pantry/<int:item_id>")
@login_required
def get_pantry_item(item_id):
    row = own_item(item_id)
    if row is None:
        return error("Item not found", 404)
    return jsonify({"item": item_json(row, client_today())})


@bp.put("/pantry/<int:item_id>")
@login_required
def edit_pantry(item_id):
    row = own_item(item_id)
    if row is None:
        return error("Item not found", 404)
    data = body()
    if not isinstance(data, dict):
        return error("Pantry item must be a JSON object")
    try:
        name = row["name"]
        if "name" in data:
            name, problem = clean_text(data.get("name"), "an item name", 1, 60)
            if problem:
                return error(problem)
        if "quantity" in data:
            qty = ps.parse_qty(data["quantity"])
        elif "qty" in data:
            qty = ps.parse_qty(data["qty"])
        else:
            qty = row["quantity"]
        unit = ps.parse_unit(data["unit"]) if "unit" in data else row["unit"]
        if "category" in data:
            cat = ps.parse_category(data["category"])
        elif "cat" in data:
            cat = ps.parse_category(data["cat"])
        else:
            cat = row["category"]
        if "expiry_date" in data:
            exp = ps.parse_expiry(data["expiry_date"])
        elif "exp" in data:
            exp = ps.parse_expiry(data["exp"])
        else:
            exp = row["expiry_date"]
    except ValueError as e:
        return error(str(e))
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    clash = db.execute(
        "SELECT 1 FROM pantry WHERE user_id = ? AND lower(name) = lower(?) AND unit = ? AND id != ?",
        (g.user_id, name, unit, item_id)).fetchone()
    if clash:
        return error("You already have this item with the same unit. Edit that one instead.", 409)
    db.execute("UPDATE pantry SET name=?, category=?, quantity=?, unit=?, expiry_date=? WHERE id=?",
               (name, cat, qty, unit, exp, item_id))
    db.commit()
    return jsonify({"item": item_json(own_item(item_id), client_today())})


@bp.patch("/pantry/<int:item_id>/quantity")
@login_required
def change_quantity(item_id):
    row = own_item(item_id)
    if row is None:
        return error("Item not found", 404)
    try:
        data = body()
        if not isinstance(data, dict):
            return error("Quantity update must be a JSON object")
        delta = float(data.get("delta"))
    except (TypeError, ValueError):
        return error("Send delta as a number, for example 1 or -1")
    if delta != delta or abs(delta) > ps.MAX_QTY:
        return error("Send delta as a number, for example 1 or -1")
    new_qty = round(row["quantity"] + delta, 2)
    db = get_db()
    if new_qty <= 0:  # reaching 0 removes the item, as the page already did
        db.execute("DELETE FROM pantry WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"deleted": True, "id": item_id})
    db.execute("UPDATE pantry SET quantity = ? WHERE id = ?", (min(new_qty, ps.MAX_QTY), item_id))
    db.commit()
    return jsonify({"item": item_json(own_item(item_id), client_today())})


@bp.delete("/pantry/<int:item_id>")
@login_required
def delete_pantry_item(item_id):
    if own_item(item_id) is None:
        return error("Item not found", 404)
    db = get_db()
    db.execute("DELETE FROM pantry WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({"ok": True})


@bp.delete("/pantry")
@login_required
def clear_pantry():
    db = get_db()
    cur = db.execute("DELETE FROM pantry WHERE user_id = ?", (g.user_id,))
    db.commit()
    return jsonify({"ok": True, "removed": cur.rowcount})
