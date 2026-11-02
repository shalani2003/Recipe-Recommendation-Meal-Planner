"""Shared helpers for every backend module (task P1 and P5).

    from auth_helpers import login_required, error, body
"""
import re
import time
from collections import defaultdict, deque
from functools import wraps
from urllib.parse import urlparse

from flask import current_app, g, jsonify, request, session

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
BAD_TEXT_RE = re.compile(r"[<>\x00-\x1f]")


def error(message, status=400):
    """Return the standard API error shape: {"error": "message"}."""
    return jsonify({"error": message}), status


def body():
    data = request.get_json(silent=True)
    return {} if data is None else data


def clean_email(value):
    return str(value or "").strip().lower()


def clean_text(value, label, min_len=1, max_len=60):
    """Trim a text value and reject markup characters. Returns (text, problem)."""
    if value is None:
        value = ""
    elif not isinstance(value, str):
        return None, "%s must be text" % label.capitalize()
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) < min_len:
        return None, "Enter %s" % label
    if len(text) > max_len:
        return None, "%s must be %d characters or fewer" % (label.capitalize(), max_len)
    if BAD_TEXT_RE.search(text):
        return None, "%s cannot contain < or > characters" % label.capitalize()
    return text, None


def password_problem(pw):
    if not isinstance(pw, str):
        return "Password must be text"
    if len(pw) < 8 or not re.search(r"\d", pw):
        return "Use 8+ characters with at least one number"
    if len(pw) > 128:
        return "Password must be 128 characters or fewer"
    return None


def login_required(view):
    """Use on every route that needs a logged-in user. Sets g.user_id."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        uid = session.get("user_id")
        if uid is None:
            return error("Not logged in", 401)
        from db import get_db
        if get_db().execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone() is None:
            session.clear()
            return error("Not logged in", 401)
        g.user_id = uid
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------- rate limit
_hits = defaultdict(deque)


def rate_limited(key, limit=8, window=300):
    """True when `key` has been used more than `limit` times in `window` seconds."""
    if not current_app.config.get("RATE_LIMIT_ENABLED", True):
        return False
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def reset_rate_limits():
    _hits.clear()


# ---------------------------------------------------- request / response guards
def install_guards(app):
    @app.before_request
    def same_origin_only():
        """Simple CSRF guard: a browser request that changes data must come from this site."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/"):
            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.host:
                return error("Cross-site requests are not allowed", 403)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'",
        )
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp
