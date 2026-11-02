from conftest import make_user


def test_register_login_me_logout(app):
    c, data = make_user(app)
    assert data["user"]["email"] == "nimal@example.com"
    assert len(data["recovery_code"]) == 14  # XXXX-XXXX-XXXX
    assert c.get("/api/me").get_json()["user"]["name"] == "Nimal"
    c.post("/api/logout")
    assert c.get("/api/me").status_code == 401
    r = c.post("/api/login", json={"email": "NIMAL@example.com ", "password": "secret123"})
    assert r.status_code == 200


def test_register_validation(client):
    bad = [({"name": "", "email": "a@b.co", "password": "secret123"}, 400),
           ({"name": "Al", "email": "nope", "password": "secret123"}, 400),
           ({"name": "Al", "email": "a@b.co", "password": "short1"}, 400),
           ({"name": "Al", "email": "a@b.co", "password": "nodigitshere"}, 400),
           ({"name": "<script>alert(1)</script>", "email": "a@b.co", "password": "secret123"}, 400)]
    for payload, status in bad:
        assert client.post("/api/register", json=payload).status_code == status, payload


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
    assert "secret123" not in row[0] and row[0].startswith(("scrypt:", "pbkdf2:"))
    assert row[1] and row[1].startswith(("scrypt:", "pbkdf2:"))


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


def test_reset_token_rejects_garbage_and_weak_password(app):
    c, data = make_user(app)
    assert c.post("/api/reset-password", json={"token": "garbage", "password": "newpass123"}).status_code == 400
    token = c.post("/api/forgot-password", json={"email": "nimal@example.com", "recovery_code": data["recovery_code"]}).get_json()["reset_token"]
    assert c.post("/api/reset-password", json={"token": token, "password": "weak"}).status_code == 400


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
