from db import get_db


def test_shopping_list_persists_items_and_bought_state(app, user, user2):
    response = user.put("/api/shopping", json={"items": [
        {"name": "Rice", "quantity": 2, "unit": "kg", "done": False},
        {"name": "Milk", "qty": 1, "unit": "l", "bought": True},
    ]})
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert [(item["name"], item["quantity"], item["unit"], item["done"]) for item in items] == [
        ("Rice", 2, "kg", False),
        ("Milk", 1, "l", True),
    ]
    assert user.get("/api/shopping").get_json() == {"items": items}
    assert user2.get("/api/shopping").get_json() == {"items": []}

    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "SELECT id FROM users WHERE email = ?", ("nimal@example.com",)
        ).fetchone()["id"]
        assert db.execute(
            "SELECT COUNT(*) FROM shopping_items WHERE user_id = ?", (user_id,)
        ).fetchone()[0] == 2
    assert user.delete("/api/shopping").get_json() == {"ok": True, "removed": 2}


def test_shopping_list_validation_and_login(client, user):
    assert client.get("/api/shopping").status_code == 401
    assert user.put("/api/shopping", json={"items": [{"name": "Rice", "done": "yes"}]}).status_code == 400
    assert user.put("/api/shopping", json={"items": [{"name": "Rice", "quantity": -1}]}).status_code == 400


def test_shopping_item_crud_duplicate_merge_and_user_isolation(app, client, user, user2):
    assert client.post("/api/shopping", json={"name": "Rice"}).status_code == 401

    response = user.post("/api/shopping", json={
        "item_name": "Rice", "qty": 2, "unit": "kg", "expiry_date": "2027-01-15",
    })
    assert response.status_code == 201
    item = response.get_json()["item"]
    assert item["name"] == item["item_name"] == "Rice"
    assert item["quantity"] == item["qty"] == 2
    assert item["expiry_date"] == "2027-01-15"
    assert item["is_bought"] is False

    merged = user.post("/api/shopping", json={
        "name": "rice", "quantity": 3, "unit": "kg", "expiry_date": "2027-01-15",
    })
    assert merged.status_code == 200
    assert merged.get_json()["merged"] is True
    assert merged.get_json()["item"]["id"] == item["id"]
    assert merged.get_json()["item"]["quantity"] == 5
    assert len(user.get("/api/shopping").get_json()["items"]) == 1
    assert user2.get(f"/api/shopping/{item['id']}").status_code == 404

    updated = user.patch(f"/api/shopping/{item['id']}", json={"is_bought": True})
    assert updated.status_code == 200
    assert updated.get_json()["item"]["done"] is True
    assert user.patch(f"/api/shopping/{item['id']}", json={"is_bought": "yes"}).status_code == 400

    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "SELECT id FROM users WHERE email = ?", ("nimal@example.com",)
        ).fetchone()["id"]
        row = db.execute(
            "SELECT qty, bought, expiry_date FROM shopping_items WHERE user_id = ? AND id = ?",
            (user_id, item["id"]),
        ).fetchone()
        assert tuple(row) == (5, 1, "2027-01-15")

    assert user.delete(f"/api/shopping/{item['id']}").get_json() == {"ok": True, "removed": 1}
    assert user.delete(f"/api/shopping/{item['id']}").status_code == 404


def test_shopping_item_rejects_bad_expiry_and_supports_clear(app, user):
    assert user.post("/api/shopping", json={
        "name": "Rice", "expiry_date": "not-a-date",
    }).status_code == 400
    user.post("/api/shopping", json={"name": "Rice", "quantity": 1})
    user.post("/api/shopping", json={"name": "Milk", "quantity": 2})
    response = user.delete("/api/shopping")
    assert response.get_json() == {"ok": True, "removed": 2}


def test_water_is_saved_per_user_and_day(app, user, user2):
    day = "2026-11-02"
    assert user.get(f"/api/water?day={day}").get_json() == {"day": day, "glasses": 0}
    response = user.put("/api/water", json={"day": day, "glasses": 4})
    assert response.status_code == 200
    assert response.get_json() == {"day": day, "glasses": 4}
    assert user.put("/api/water", json={"day": day, "glasses": 5}).status_code == 200
    assert user.get(f"/api/water?day={day}").get_json()["glasses"] == 5
    assert user2.get(f"/api/water?day={day}").get_json()["glasses"] == 0
    assert user.put("/api/water", json={"day": day, "glasses": True}).status_code == 400
    assert user.get("/api/water?day=not-a-date").status_code == 400

    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "SELECT id FROM users WHERE email = ?", ("nimal@example.com",)
        ).fetchone()["id"]
        assert db.execute(
            "SELECT glasses FROM water WHERE user_id = ? AND day = ?", (user_id, day)
        ).fetchone()[0] == 5


def test_weight_log_api_and_profile_updates_are_recorded(app, user, user2):
    response = user.post("/api/weight-log", json={
        "weight_kg": 72.5, "logged_on": "2026-11-02",
    })
    assert response.status_code == 201
    entry = response.get_json()["entry"]
    assert entry["id"]
    assert entry["weight_kg"] == 72.5
    assert entry["logged_on"] == "2026-11-02"
    assert user.get("/api/weight-log").get_json()["entries"][0]["weight_kg"] == 72.5
    assert user2.get("/api/weight-log").get_json() == {"entries": []}
    assert user.post("/api/weight-log", json={"weight_kg": 251}).status_code == 400

    assert user.put("/api/profile", json={"weight": 70}).status_code == 200
    assert user.put("/api/profile", json={"weight": 70}).status_code == 200
    entries = user.get("/api/weight-log").get_json()["entries"]
    assert [entry["weight_kg"] for entry in entries].count(70) == 1
    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "SELECT id FROM users WHERE email = ?", ("nimal@example.com",)
        ).fetchone()["id"]
        assert db.execute(
            "SELECT COUNT(*) FROM weight_log WHERE user_id = ?", (user_id,)
        ).fetchone()[0] == 2
