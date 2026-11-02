import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from auth_helpers import reset_rate_limits  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    reset_rate_limits()
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DB_PATH": str(tmp_path / "test.db"),
        "UPLOAD_DIR": str(tmp_path / "uploads"),
        "RECIPE_IMAGE_DIR": str(tmp_path / "food"),
        "RATE_LIMIT_ENABLED": False,
    })


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(app, name="Nimal", email="nimal@example.com", pw="secret123"):
    """Register a new user on its own client (own cookie jar). Returns (client, response json)."""
    c = app.test_client()
    r = c.post("/api/register", json={"name": name, "email": email, "password": pw})
    assert r.status_code == 201, r.get_json()
    return c, r.get_json()


@pytest.fixture()
def user(app):
    c, data = make_user(app)
    return c


@pytest.fixture()
def user2(app):
    c, data = make_user(app, "Kamala", "kamala@example.com")
    return c
