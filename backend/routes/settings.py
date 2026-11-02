"""Settings, password change, profile picture and "reset all data" (tasks P6 and P7)."""
import json
import os
import secrets

from flask import Blueprint, current_app, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

from auth_helpers import (EMAIL_RE, body, clean_email, clean_text, error, login_required,
                          password_problem, rate_limited)
from db import USER_DATA_TABLES, get_db
from routes.auth import new_recovery_code, norm_code

bp = Blueprint("settings", __name__, url_prefix="/api")

NOTIFICATION_MODES = ["all", "important", "off"]
DEFAULT_PREFS = {"notificationMode": "all", "mealReminders": True, "weeklySummary": True}
MAX_PICTURE_BYTES = 2 * 1024 * 1024


def read_prefs(db, user_id):
    row = db.execute("SELECT preferences FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    prefs = dict(DEFAULT_PREFS)
    legacy = db.execute("SELECT prefs FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    if legacy and legacy["prefs"]:
        prefs.update(json.loads(legacy["prefs"]))
    if row and row["preferences"]:
        prefs.update(json.loads(row["preferences"]))
    return prefs


def settings_json(db, user_id):
    u = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    setting = db.execute(
        "SELECT profile_picture FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    picture = setting["profile_picture"] if setting and setting["profile_picture"] else u["picture"]
    return {"name": u["name"], "email": u["email"], "preferences": read_prefs(db, user_id),
            "picture_url": ("/api/settings/picture?v=" + picture) if picture else None,
            "has_recovery_code": bool(u["recovery_hash"])}


@bp.get("/settings")
@login_required
def get_settings():
    return jsonify(settings_json(get_db(), g.user_id))


@bp.put("/settings")
@login_required
def put_settings():
    data = body()
    if not isinstance(data, dict):
        return error("Settings must be a JSON object")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (g.user_id,)).fetchone()
    name, email = user["name"], user["email"]

    if "name" in data:
        name, problem = clean_text(data["name"], "your name", 2, 60)
        if problem:
            return error(problem)
    if "email" in data:
        email = clean_email(data["email"])
        if not EMAIL_RE.match(email) or len(email) > 120:
            return error("Enter a valid email")
        if db.execute("SELECT 1 FROM users WHERE email = ? AND id != ?", (email, g.user_id)).fetchone():
            return error("Another account already uses this email.", 409)

    prefs = read_prefs(db, g.user_id)
    if "preferences" in data:
        incoming = data["preferences"]
        if not isinstance(incoming, dict):
            return error("preferences must be an object")
        if "notificationMode" in incoming:
            if incoming["notificationMode"] not in NOTIFICATION_MODES:
                return error("notificationMode must be one of: " + ", ".join(NOTIFICATION_MODES))
            prefs["notificationMode"] = incoming["notificationMode"]
        for key in ("mealReminders", "weeklySummary"):
            if key in incoming:
                if not isinstance(incoming[key], bool):
                    return error("%s must be true or false" % key)
                prefs[key] = incoming[key]

    db.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (name, email, g.user_id))
    db.execute("UPDATE profiles SET name = ? WHERE user_id = ?", (name, g.user_id))
    db.execute("INSERT INTO settings (user_id, preferences) VALUES (?, ?) "
               "ON CONFLICT(user_id) DO UPDATE SET preferences = excluded.preferences",
               (g.user_id, json.dumps(prefs)))
    db.execute("INSERT INTO user_settings (user_id, prefs) VALUES (?, ?) "
               "ON CONFLICT(user_id) DO UPDATE SET prefs = excluded.prefs", (g.user_id, json.dumps(prefs)))
    db.commit()
    return jsonify(settings_json(db, g.user_id))


@bp.post("/settings/password")
@login_required
def change_password():
    data = body()
    if not isinstance(data, dict):
        return error("Password details must be a JSON object")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (g.user_id,)).fetchone()
    if rate_limited("chpw:%s" % g.user_id, limit=8, window=300):
        return error("Too many attempts. Wait a few minutes and try again.", 429)
    current_password = data.get("current_password")
    new_pw = data.get("new_password")
    if not isinstance(current_password, str) or not isinstance(new_pw, str):
        return error("Enter your current and new password")
    if not check_password_hash(user["password_hash"], current_password):
        return error("Your current password is incorrect.", 403)
    problem = password_problem(new_pw)
    if problem:
        return error(problem)
    if new_pw == str(data.get("current_password")):
        return error("Choose a password different from the current one")
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_pw), g.user_id))
    db.commit()
    return jsonify({"ok": True})


@bp.post("/settings/recovery-code")
@login_required
def new_code():
    """Make a new recovery code (needed for accounts made before recovery codes existed)."""
    data = body()
    if not isinstance(data, dict):
        return error("Password details must be a JSON object")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (g.user_id,)).fetchone()
    password = data.get("password")
    if not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return error("Your password is incorrect.", 403)
    code = new_recovery_code()
    db.execute("UPDATE users SET recovery_hash = ? WHERE id = ?", (generate_password_hash(norm_code(code)), g.user_id))
    db.commit()
    return jsonify({"recovery_code": code})


# ------------------------------------------------------------ profile picture
def sniff_image(head):
    """Look at the real bytes, not the file name. Returns the extension or None."""
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


def avatar_dir():
    path = os.path.join(current_app.config["UPLOAD_DIR"], "avatars")
    os.makedirs(path, exist_ok=True)
    return path


def remove_picture_file(filename):
    if filename:
        try:
            os.remove(os.path.join(avatar_dir(), os.path.basename(filename)))
        except OSError:
            pass


@bp.post("/settings/picture")
@login_required
def upload_picture():
    f = request.files.get("picture")
    if f is None or not f.filename:
        return error("Choose a picture to upload")
    data = f.read(MAX_PICTURE_BYTES + 1)
    if len(data) > MAX_PICTURE_BYTES:
        return error("Choose an image smaller than 2 MB.", 413)
    ext = sniff_image(data[:16])
    if ext is None:
        return error("Choose a JPG, PNG or WebP image.", 415)

    db = get_db()
    old = db.execute("SELECT picture FROM users WHERE id = ?", (g.user_id,)).fetchone()["picture"]
    filename = "u%d-%s%s" % (g.user_id, secrets.token_hex(6), ext)
    with open(os.path.join(avatar_dir(), filename), "wb") as out:
        out.write(data)
    db.execute("UPDATE users SET picture = ? WHERE id = ?", (filename, g.user_id))
    db.execute("INSERT INTO settings (user_id, profile_picture) VALUES (?, ?) "
               "ON CONFLICT(user_id) DO UPDATE SET profile_picture = excluded.profile_picture",
               (g.user_id, filename))
    db.commit()
    remove_picture_file(old)
    return jsonify({"picture_url": "/api/settings/picture?v=" + filename}), 201


@bp.get("/settings/picture")
@login_required
def get_picture():
    db = get_db()
    row = db.execute("SELECT profile_picture FROM settings WHERE user_id = ?", (g.user_id,)).fetchone()
    picture = row["profile_picture"] if row and row["profile_picture"] else None
    if picture is None:
        picture = db.execute("SELECT picture FROM users WHERE id = ?", (g.user_id,)).fetchone()["picture"]
    if not picture:
        return error("No picture", 404)
    return send_from_directory(avatar_dir(), picture)


@bp.delete("/settings/picture")
@login_required
def delete_picture():
    db = get_db()
    row = db.execute("SELECT picture FROM users WHERE id = ?", (g.user_id,)).fetchone()
    remove_picture_file(row["picture"])
    db.execute("UPDATE users SET picture = NULL WHERE id = ?", (g.user_id,))
    db.execute("INSERT INTO settings (user_id, profile_picture) VALUES (?, NULL) "
               "ON CONFLICT(user_id) DO UPDATE SET profile_picture = NULL", (g.user_id,))
    db.commit()
    return jsonify({"ok": True})


# -------------------------------------------------------------- reset all data
@bp.delete("/account/data")
@login_required
def reset_account_data():
    """Delete this user's data only (pantry, diets, plan, shopping, health, settings, picture).
    The account and login are kept, and the answer says so."""
    data = body()
    if not isinstance(data, dict):
        return error("Confirmation must be a JSON object")
    if data.get("confirm") is not True:
        return error('Send {"confirm": true} to reset all data')
    db = get_db()
    row = db.execute("SELECT picture FROM users WHERE id = ?", (g.user_id,)).fetchone()
    remove_picture_file(row["picture"])
    for table in USER_DATA_TABLES:
        db.execute("DELETE FROM %s WHERE user_id = ?" % table, (g.user_id,))
    db.execute("UPDATE users SET picture = NULL WHERE id = ?", (g.user_id,))
    db.commit()
    return jsonify({"ok": True, "account_kept": True, "logged_in": True,
                    "message": "Your saved data was deleted. Your account and login were not changed."})
