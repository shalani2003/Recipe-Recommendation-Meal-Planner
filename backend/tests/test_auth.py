from conftest import make_user


def test_register_login_me_logout(app):
    c, data = make_user(app)
    assert data["user"]["email"] == "nimal@example.com"
    assert len(data["recovery_code"]) == 14  # XXXX-XXXX-XXXX
    assert "password" not in data and "password_hash" not in data["user"]
    assert c.get("/api/me").get_json()["user"]["name"] == "Nimal"
    c.post("/api/logout")
    assert c.get("/api/me").status_code == 401
    r = c.post("/api/login", json={"email": "NIMAL@example.com ", "password": "secret123"})
    assert r.status_code == 200
    assert "secret123" not in r.get_data(as_text=True)
    assert "password_hash" not in r.get_json()["user"]


def test_register_validation(client):
    bad = [({"name": "", "email": "a@b.co", "password": "secret123"}, 400),
           ({"name": 123, "email": "a@b.co", "password": "secret123"}, 400),
           ({"name": "Al", "email": "nope", "password": "secret123"}, 400),
           ({"name": "Al", "email": "a@b.co", "password": "short1"}, 400),
           ({"name": "Al", "email": "a@b.co", "password": {"value": "secret123"}}, 400),
           ({"name": "Al", "email": "a@b.co", "password": "nodigitshere"}, 400)]
    for payload, status in bad:
        assert client.post("/api/register", json=payload).status_code == status, payload
    response = client.post("/api/register", json={
        "name": "<script>alert('test')</script>",
        "email": "script@example.com",
        "password": "secret123",
    })
    assert response.status_code == 201
    assert response.get_json()["user"]["name"] == "<script>alert('test')</script>"


def test_duplicate_email_case_insensitive(app):
    make_user(app)
    r = app.test_client().post("/api/register", json={"name": "X Y", "email": "NIMAL@EXAMPLE.COM", "password": "secret123"})
    assert r.status_code == 409


def test_wrong_password_and_unknown_email_same_message(app):
    make_user(app)
    c = app.test_client()
    a = c.post("/api/login", json={"email": "nimal@example.com", "password": "wrongpass1"})
    b = c.post("/api/login", json={"email": "nobody@example.com", "password": "wrongpass1"})
    assert a.status_code == b.status_code == 401
    assert a.get_json() == b.get_json()


def test_login_rate_limit(app):
    app.config["RATE_LIMIT_ENABLED"] = True
    make_user(app)
    c = app.test_client()
    codes = [c.post("/api/login", json={"email": "nimal@example.com", "password": "bad-pass1"}).status_code for _ in range(10)]
    assert 429 in codes


def test_passwords_are_hashed(app):
    make_user(app)
    import sqlite3
    row = sqlite3.connect(app.config["DB_PATH"]).execute("SELECT password_hash, recovery_hash FROM users").fetchone()
    assert "secret123" not in row[0] and row[0].startswith("$argon2id$")
    assert row[1] and row[1].startswith("$argon2id$")


def test_registration_stops_if_secure_hashing_fails(app, monkeypatch):
    from routes import auth
    from services.passwords import PasswordHashError

    def fail_hashing(_secret):
        raise PasswordHashError

    monkeypatch.setattr(auth, "hash_password", fail_hashing)
    client = app.test_client()
    response = client.post("/api/register", json={
        "name": "Nimal", "email": "nimal@example.com", "password": "secret123",
    })

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "Unable to securely process your password. Please try again later."
    }
    assert "secret123" not in response.get_data(as_text=True)
    assert client.post("/api/login", json={
        "email": "nimal@example.com", "password": "secret123",
    }).status_code == 401


def test_legacy_password_hashes_remain_login_compatible(app):
    from werkzeug.security import generate_password_hash
    from db import get_db

    client = app.test_client()
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Legacy User", "legacy@example.com", generate_password_hash(
                "legacy123", method="scrypt:32768:8:1"
            )),
        )
        db.commit()

    assert client.post("/api/login", json={
        "email": "legacy@example.com", "password": "legacy123",
    }).status_code == 200
    assert client.post("/api/login", json={
        "email": "legacy@example.com", "password": "wrong123",
    }).status_code == 401


def test_reset_needs_recovery_code(app):
    c, data = make_user(app)
    code = data["recovery_code"]
    other = app.test_client()
    # wrong code and unknown email give the same answer
    a = other.post("/api/forgot-password", json={"email": "nimal@example.com", "recovery_code": "AAAA-AAAA-AAAA"})
    b = other.post("/api/forgot-password", json={"email": "ghost@example.com", "recovery_code": code})
    assert a.status_code == b.status_code == 400 and a.get_json() == b.get_json()
    # old one-step reset (email + password only) no longer works
    assert other.post("/api/reset-password", json={"email": "nimal@example.com", "password": "newpass123"}).status_code == 400

    t = other.post("/api/forgot-password", json={"email": "nimal@example.com", "recovery_code": code.lower()})
    assert t.status_code == 200
    token = t.get_json()["reset_token"]
    r = other.post("/api/reset-password", json={"token": token, "password": "newpass123"})
    assert r.status_code == 200 and r.get_json()["recovery_code"] != code
    # token works once only
    assert other.post("/api/reset-password", json={"token": token, "password": "another123"}).status_code == 400
    # new password works, old one does not, old recovery code is dead
    assert other.post("/api/login", json={"email": "nimal@example.com", "password": "newpass123"}).status_code == 200
    assert other.post("/api/login", json={"email": "nimal@example.com", "password": "secret123"}).status_code == 401
    assert other.post("/api/forgot-password", json={"email": "nimal@example.com", "recovery_code": code}).status_code == 400


def test_reset_token_expires(app, monkeypatch):
    import time
    from itsdangerous.timed import TimestampSigner
    from routes import auth

    client, data = make_user(app)
    original_timestamp = TimestampSigner.get_timestamp
    with monkeypatch.context() as patch:
        patch.setattr(
            TimestampSigner,
            "get_timestamp",
            lambda signer: int(time.time()) - auth.RESET_TOKEN_SECONDS - 1,
        )
        token_response = client.post("/api/forgot-password", json={
            "email": "nimal@example.com",
            "recovery_code": data["recovery_code"],
        })
    assert token_response.status_code == 200

    expired = client.post("/api/reset-password", json={
        "token": token_response.get_json()["reset_token"],
        "password": "newpass123",
    })
    assert expired.status_code == 400
    assert expired.get_json() == {
        "error": "This reset link is not valid or has expired. Start again."
    }
    assert client.post("/api/login", json={
        "email": "nimal@example.com", "password": "secret123",
    }).status_code == 200
    assert TimestampSigner.get_timestamp is original_timestamp


def test_reset_without_ownership_proof_does_not_change_password(app):
    client, _ = make_user(app)
    no_token = client.post("/api/reset-password", json={
        "email": "nimal@example.com", "password": "newpass123",
    })
    bad_code = client.post("/api/forgot-password", json={
        "email": "nimal@example.com", "recovery_code": "AAAA-AAAA-AAAA",
    })
    unknown_account = client.post("/api/forgot-password", json={
        "email": "ghost@example.com", "recovery_code": "AAAA-AAAA-AAAA",
    })

    assert no_token.status_code == 400
    assert bad_code.status_code == unknown_account.status_code == 400
    assert bad_code.get_json() == unknown_account.get_json()
    assert client.post("/api/login", json={
        "email": "nimal@example.com", "password": "secret123",
    }).status_code == 200


def test_reset_token_rejects_garbage_and_weak_password(app):
    c, data = make_user(app)
    assert c.post("/api/reset-password", json={"token": "garbage", "password": "newpass123"}).status_code == 400
    assert c.post("/api/reset-password", json={"token": "garbage", "password": {"value": "newpass123"}}).status_code == 400
    token = c.post("/api/forgot-password", json={"email": "nimal@example.com", "recovery_code": data["recovery_code"]}).get_json()["reset_token"]
    assert c.post("/api/reset-password", json={"token": token, "password": "weak"}).status_code == 400


def test_reset_code_issues_only_one_effective_reset(app):
    c, data = make_user(app)
    payload = {"email": "nimal@example.com", "recovery_code": data["recovery_code"]}
    first = c.post("/api/forgot-password", json=payload).get_json()["reset_token"]
    second = c.post("/api/forgot-password", json=payload).get_json()["reset_token"]

    assert c.post("/api/reset-password", json={"token": first, "password": "newpass123"}).status_code == 200
    assert c.post("/api/reset-password", json={"token": second, "password": "another123"}).status_code == 400


def test_api_requires_login(client):
    for method, path in [("get", "/api/pantry"), ("get", "/api/dietary"), ("get", "/api/settings"),
                         ("get", "/api/me"), ("delete", "/api/account/data")]:
        assert getattr(client, method)(path).status_code == 401, path


def test_cross_site_write_blocked_and_headers(user):
    r = user.post("/api/pantry", json={"name": "Rice"}, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    r = user.get("/api/pantry")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors" in r.headers["Content-Security-Policy"]
