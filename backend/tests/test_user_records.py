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


def test_markup_like_shopping_names_are_preserved_for_safe_text_rendering(user):
    names = [
        "<script>alert('test')</script>",
        "<img src=x onerror=alert(1)>",
        "<b>Test Name</b>",
        "Farmer's \"special\" 魚",
    ]
    response = user.put("/api/shopping", json={
        "items": [{"name": name, "quantity": 1, "unit": "pcs"} for name in names],
    })
    assert response.status_code == 200
    assert [item["name"] for item in response.get_json()["items"]] == names


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


def test_move_bought_shopping_item_is_atomic_and_retry_safe(user):
    existing = user.post("/api/pantry", json={
        "name": "Rice", "category": "Grains", "quantity": 1, "unit": "kg",
        "expiry_date": "2027-02-01",
    })
    assert existing.status_code == 201
    shopping = user.post("/api/shopping", json={
        "name": "Rice", "quantity": 0.5, "unit": "kg", "done": True,
    }).get_json()["item"]
    move_url = f"/api/shopping/{shopping['id']}/move-to-pantry"
    payload = {
        "category": "Grains", "quantity": 0.5, "unit": "kg",
        "expiry_date": "2027-01-01",
    }

    moved = user.post(move_url, json=payload)
    assert moved.status_code == 200
    assert moved.get_json() == {"ok": True, "merged": True, "removed": 1}
    retry = user.post(move_url, json=payload)
    assert retry.status_code == 404

    pantry_items = user.get("/api/pantry").get_json()["items"]
    rice = next(item for item in pantry_items if item["name"].lower() == "rice")
    assert (rice["quantity"], rice["unit"], rice["category"], rice["expiry_date"]) == (
        1.5, "kg", "Grains", "2027-01-01",
    )
    assert all(item["id"] != shopping["id"] for item in user.get("/api/shopping").get_json()["items"])


def test_move_rejects_unbought_or_invalid_pantry_data_without_removing_shopping(user):
    shopping = user.post("/api/shopping", json={
        "name": "Rice", "quantity": 1, "unit": "kg", "done": False,
    }).get_json()["item"]
    move_url = f"/api/shopping/{shopping['id']}/move-to-pantry"
    payload = {"category": "Grains", "quantity": 1, "unit": "kg"}
    assert user.post(move_url, json=payload).status_code == 400
    user.patch(f"/api/shopping/{shopping['id']}", json={"is_bought": True})
    assert user.post(move_url, json={**payload, "category": "Invalid"}).status_code == 400
    assert len(user.get("/api/shopping").get_json()["items"]) == 1
    assert user.post(move_url, json={**payload, "category": ""}).status_code == 200
    assert user.get("/api/shopping").get_json()["items"] == []


def test_markup_like_shopping_names_move_to_pantry_as_literal_text(user):
    names = [
        "<script>alert('test')</script>",
        "<img src=x onerror=alert(1)>",
        "<b>Test Name</b>",
    ]
    for name in names:
        shopping = user.post("/api/shopping", json={
            "name": name, "quantity": 1, "unit": "pcs", "done": True,
        }).get_json()["item"]
        response = user.post(
            f"/api/shopping/{shopping['id']}/move-to-pantry",
            json={"quantity": 1, "unit": "pcs"},
        )
        assert response.status_code == 200
        pantry = user.get("/api/pantry").get_json()["items"]
        assert sum(item["name"] == name for item in pantry) == 1
        assert next(item for item in pantry if item["name"] == name)["category"] == "Other"
    assert user.get("/api/shopping").get_json()["items"] == []


def test_clear_shopping_does_not_clear_pantry(user):
    user.post("/api/pantry", json={
        "name": "Rice", "category": "Grains", "quantity": 1, "unit": "kg",
    })
    user.post("/api/shopping", json={"name": "Milk"})

    response = user.delete("/api/shopping")

    assert response.get_json() == {"ok": True, "removed": 1}
    assert user.get("/api/shopping").get_json()["items"] == []
    assert any(item["name"] == "Rice" for item in user.get("/api/pantry").get_json()["items"])


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
