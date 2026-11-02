"""Authentication helpers for the API modules."""
from functools import wraps

from flask import jsonify, session

from database import get_db


def current_user_id():
    """Id of the logged-in user (only meaningful inside @login_required views)."""
    return session.get("user_id")


def login_required(view):
    """
    Protect an API route. Returns 401 JSON unless the session belongs to a user
    that still exists (e.g. after vitaplate.db was deleted during development
    an old cookie must not be accepted).
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        uid = session.get("user_id")
        if uid is None:
            return jsonify({"error": "Not logged in"}), 401
        if get_db().execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone() is None:
            session.clear()
            return jsonify({"error": "Not logged in"}), 401
        return view(*args, **kwargs)

    return wrapper
