"""Dietary restrictions, allergies and the onboarding flag (task P4)."""
import json

from flask import Blueprint, g, jsonify

from auth_helpers import BAD_TEXT_RE, body, error, login_required
from db import get_db

bp = Blueprint("dietary", __name__, url_prefix="/api")

DIETS = ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Nut-free", "Halal", "Low sugar"]
MAX_ALLERGIES = 20


def read(db, user_id):
    row = db.execute("SELECT * FROM dietary WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return {"diets": [], "allergies": [], "onboarding_completed": False}
    return {"diets": json.loads(row["diets"]), "allergies": json.loads(row["allergies"]),
            "onboarding_completed": bool(row["onboarding_completed"])}


@bp.get("/dietary")
@login_required
def get_dietary():
    return jsonify(read(get_db(), g.user_id))


@bp.put("/dietary")
@login_required
def put_dietary():
    """Send any of: diets, allergies, onboarding_completed. Missing keys are left unchanged."""
    data = body()
    db = get_db()
    cur = read(db, g.user_id)

    if "diets" in data:
        if not isinstance(data["diets"], list):
            return error("diets must be a list")
        unknown = [d for d in data["diets"] if d not in DIETS]
        if unknown:
            return error("Unknown diet: %s" % unknown[0])
        cur["diets"] = [d for d in DIETS if d in data["diets"]]

    if "allergies" in data:
        if not isinstance(data["allergies"], list):
            return error("allergies must be a list")
        clean = []
        for a in data["allergies"]:
            text = " ".join(str(a or "").split()).lower()
            if not text:
                continue
            if len(text) > 40 or BAD_TEXT_RE.search(text):
                return error("Each allergy must be 40 characters or fewer and plain text")
            if text not in clean:
                clean.append(text)
        if len(clean) > MAX_ALLERGIES:
            return error("You can list up to %d allergies" % MAX_ALLERGIES)
        cur["allergies"] = clean

    if "onboarding_completed" in data:
        cur["onboarding_completed"] = bool(data["onboarding_completed"])

    db.execute(
        "INSERT INTO dietary (user_id, diets, allergies, onboarding_completed) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET diets=excluded.diets, allergies=excluded.allergies, "
        "onboarding_completed=excluded.onboarding_completed",
        (g.user_id, json.dumps(cur["diets"]), json.dumps(cur["allergies"]), int(cur["onboarding_completed"])))
    db.commit()
    return jsonify(cur)
