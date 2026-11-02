"""Register, login, logout, current user, password reset (tasks P1 and P5)."""
import secrets

from flask import Blueprint, current_app, jsonify, request, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from auth_helpers import (EMAIL_RE, body, clean_email, clean_text, error,
                          login_required, password_problem, rate_limited)
from db import get_db, seed_new_user

bp = Blueprint("auth", __name__, url_prefix="/api")

RESET_TOKEN_SECONDS = 15 * 60
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def new_recovery_code():
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))
    return "-".join(raw[i:i + 4] for i in range(0, 12, 4))


def norm_code(value):
    return str(value or "").upper().replace("-", "").replace(" ", "")


def public_user(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def login_user(row):
    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]


def serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="vitaplate-pw-reset")


@bp.post("/register")
def register():
    data = body()
    if not isinstance(data, dict):
        return error("Registration details must be a JSON object")
    name, problem = clean_text(data.get("name"), "your name", 2, 60)
    if problem:
        return error(problem)
    email = clean_email(data.get("email"))
    if not EMAIL_RE.match(email) or len(email) > 120:
        return error("Enter a valid email")
    pw = str(data.get("password") or "")
    problem = password_problem(pw)
    if problem:
        return error(problem)

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        return error("An account with this email already exists. Try logging in.", 409)

    code = new_recovery_code()
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash, recovery_hash) VALUES (?,?,?,?)",
        (name, email, generate_password_hash(pw), generate_password_hash(norm_code(code))),
    )
    seed_new_user(db, cur.lastrowid)
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    login_user(row)
    # The recovery code is shown once. Only its hash is stored.
    return jsonify({"user": public_user(row), "recovery_code": code}), 201


@bp.post("/login")
def login():
    data = body()
    if not isinstance(data, dict):
        return error("Login details must be a JSON object")
    email = clean_email(data.get("email"))
    pw = str(data.get("password") or "")
    if not EMAIL_RE.match(email):
        return error("Enter a valid email")
    if not pw:
        return error("Enter your password")
    if rate_limited("login:%s:%s" % (request.remote_addr, email), limit=8, window=300):
        return error("Too many attempts. Wait a few minutes and try again.", 429)

    row = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], pw):
        return error("Email or password is incorrect.", 401)
    login_user(row)
    return jsonify({"user": public_user(row)})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/me")
@login_required
def me():
    from flask import g
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (g.user_id,)).fetchone()
    return jsonify({"user": public_user(row)})


@bp.post("/forgot-password")
def forgot_password():
    """Step 1 of a reset: prove ownership with the recovery code given at registration.

    The answer is the same whether the email exists or not, so the endpoint cannot be used
    to find out which emails are registered.
    """
    data = body()
    if not isinstance(data, dict):
        return error("Recovery details must be a JSON object")
    email = clean_email(data.get("email"))
    code = norm_code(data.get("recovery_code"))
    generic = error("Email or recovery code is incorrect.", 400)
    if not EMAIL_RE.match(email) or not code:
        return generic
    if rate_limited("forgot:%s:%s" % (request.remote_addr, email), limit=5, window=900):
        return error("Too many attempts. Wait a few minutes and try again.", 429)

    row = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not row["recovery_hash"] or not check_password_hash(row["recovery_hash"], code):
        return generic
    # The token is tied to the current password hash, so it works only once.
    token = serializer().dumps({"uid": row["id"], "fp": row["password_hash"][-16:]})
    return jsonify({"reset_token": token, "expires_in": RESET_TOKEN_SECONDS})


@bp.post("/reset-password")
def reset_password():
    """Step 2: set the new password with the token from /api/forgot-password."""
    data = body()
    if not isinstance(data, dict):
        return error("Password reset details must be a JSON object")
    pw = str(data.get("password") or "")
    problem = password_problem(pw)
    if problem:
        return error(problem)
    bad_token = error("This reset link is not valid or has expired. Start again.", 400)
    try:
        info = serializer().loads(str(data.get("token") or ""), max_age=RESET_TOKEN_SECONDS)
    except (BadSignature, SignatureExpired):
        return bad_token

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (info.get("uid"),)).fetchone()
    if row is None or row["password_hash"][-16:] != info.get("fp"):
        return bad_token

    code = new_recovery_code()  # the old code is replaced after every reset
    db.execute(
        "UPDATE users SET password_hash = ?, recovery_hash = ? WHERE id = ?",
        (generate_password_hash(pw), generate_password_hash(norm_code(code)), row["id"]),
    )
    db.commit()
    session.clear()
    return jsonify({"ok": True, "recovery_code": code})
