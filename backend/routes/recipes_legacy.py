"""Temporary recipes API ported from server.js so the app runs on ONE server (task P2).

It is used only while routes/recipes.py (task J1 to J4, S. Y. S. Jayathilaka) does not exist.
When that file is added, app.py loads it instead and this file can be deleted.
Same URLs and same JSON shape as the old Node API.
"""
import json
import os
import secrets

from flask import Blueprint, current_app, g, jsonify, request, session

from auth_helpers import error, login_required
from db import get_db
from routes.settings import sniff_image

bp = Blueprint("recipes_legacy", __name__, url_prefix="/api")
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def recipe_json(r, user_id=None):
    return {"id": r["id"], "name": r["name"], "ingredients": json.loads(r["ingredients"]),
            "instructions": r["instructions"], "image": r["image"],
            "is_owner": user_id is not None and r["owner_user_id"] == user_id}


@bp.get("/recipes")
def list_recipes():  # public, like the old Node API
    user_id = session.get("user_id")
    rows = get_db().execute(
        "SELECT * FROM recipes WHERE owner_user_id IS NULL OR owner_user_id = ? ORDER BY id",
        (user_id,),
    )
    return jsonify([recipe_json(r, user_id) for r in rows])


@bp.post("/recipes")
@login_required
def add_recipe():
    name = " ".join(str(request.form.get("name") or "").split())
    ingredients = [i.strip() for i in str(request.form.get("ingredients") or "").split(",") if i.strip()]
    instructions = str(request.form.get("instructions") or "").strip()
    photo = request.files.get("imageFile")
    if not name:
        return error("Recipe name is required")
    if not ingredients:
        return error("At least one ingredient is required")
    if not instructions:
        return error("Instructions are required")
    if len(name) > 80 or "<" in name or ">" in name:
        return error("Recipe name must be 80 characters or fewer and plain text.")
    image_path = ""
    if photo is not None and photo.filename:  # the photo is optional
        data = photo.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            return error("Choose a photo smaller than 5 MB.", 413)
        ext = sniff_image(data[:16])
        if ext is None:
            return error("Choose a JPG, PNG, or WebP image.", 415)
        folder = current_app.config["RECIPE_IMAGE_DIR"]
        os.makedirs(folder, exist_ok=True)
        filename = "recipe-%s%s" % (secrets.token_hex(8), ext)
        with open(os.path.join(folder, filename), "wb") as out:
            out.write(data)
        image_path = "/assets/food/" + filename
    db = get_db()
    cur = db.execute(
        "INSERT INTO recipes (owner_user_id, name, ingredients, instructions, image) VALUES (?,?,?,?,?)",
        (g.user_id, name, json.dumps(ingredients), instructions, image_path),
    )
    db.commit()
    recipe = recipe_json(db.execute("SELECT * FROM recipes WHERE id = ?", (cur.lastrowid,)).fetchone(), g.user_id)
    return jsonify({"success": True, "message": "Recipe saved successfully", "recipe": recipe}), 201


@bp.delete("/recipes/<int:recipe_id>")
@login_required
def delete_recipe(recipe_id):
    """Only the account that added a recipe can remove it."""
    db = get_db()
    cursor = db.execute(
        "DELETE FROM recipes WHERE id = ? AND owner_user_id = ?", (recipe_id, g.user_id)
    )
    if cursor.rowcount == 0:
        return error("Recipe not found", 404)
    db.commit()
    return jsonify({"success": True})
