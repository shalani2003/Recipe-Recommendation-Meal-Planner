"""VitaPlate backend (Flask + SQLite) - ONE server for the pages and the whole API.

Run:  python app.py   ->  http://127.0.0.1:5000/login.html

Teammates add their module as routes/<name>.py with a Blueprint called `bp`
(url_prefix="/api"). It is loaded automatically; no change to this file is needed.
"""
import importlib
import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, redirect, request

import auth_helpers
import db as database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "vitaplate")

# Modules owned by the other backend developers. Loaded when the file exists.
OPTIONAL_MODULES = ["routes.recommend", "routes.shopping", "routes.plan", "routes.nutrition",
                    "routes.health", "routes.dashboard"]


def load_secret_key(path):
    """One secret key kept between restarts so logins stay valid."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


def optional_blueprint(app, module_name):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:  # a real missing library inside the module: show it
            raise
        return False
    app.register_blueprint(module.bp)
    return True


def create_app(test_config=None):
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.config.update(
        DB_PATH=os.path.join(BASE_DIR, "vitaplate.db"),
        UPLOAD_DIR=os.path.join(BASE_DIR, "uploads"),
        RECIPE_IMAGE_DIR=os.path.join(FRONTEND_DIR, "assets", "food"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        RATE_LIMIT_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = load_secret_key(os.path.join(BASE_DIR, "secret.key"))

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    database.init_db(app.config["DB_PATH"])
    database.import_recipes_json(app.config["DB_PATH"], os.path.join(BASE_DIR, "recipes.json"))
    app.teardown_appcontext(database.close_db)
    auth_helpers.install_guards(app)

    from routes import auth, dietary, pantry, profile, settings
    for module in (auth, pantry, dietary, settings, profile):
        app.register_blueprint(module.bp)
    if not optional_blueprint(app, "routes.recipes"):
        from routes import recipes_legacy
        app.register_blueprint(recipes_legacy.bp)
    for name in OPTIONAL_MODULES:
        optional_blueprint(app, name)

    @app.route("/")
    def home():
        return redirect("/login.html")

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return auth_helpers.error("Not found", 404)
        return "Page not found", 404

    @app.errorhandler(405)
    def not_allowed(_e):
        return auth_helpers.error("Method not allowed", 405)

    @app.errorhandler(413)
    def too_large(_e):
        return auth_helpers.error("The upload is too large", 413)

    @app.errorhandler(500)
    def server_error(_e):
        return auth_helpers.error("Something went wrong on the server", 500)

    return app


if __name__ == "__main__":
    # Debug mode only when asked for: set VITAPLATE_DEBUG=1 while developing.
    create_app().run(host="127.0.0.1", port=5000, debug=os.environ.get("VITAPLATE_DEBUG") == "1")
