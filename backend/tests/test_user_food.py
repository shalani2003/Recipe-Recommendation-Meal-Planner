from db import get_db


def test_favorites_and_ratings_are_saved_for_the_user(app, user, user2):
    recipe = {"name": "Test Lentil Bowl", "ingredients": ["lentils", "rice"]}
    assert user.post("/api/favorites", json=recipe).status_code == 201
    assert user.put("/api/ratings", json={**recipe, "stars": 4}).status_code == 200

    assert user.get("/api/favorites").get_json() == {"favorites": ["Test Lentil Bowl"]}
    assert user.get("/api/ratings").get_json() == {"ratings": {"Test Lentil Bowl": 4}}
    assert user2.get("/api/favorites").get_json() == {"favorites": []}
    assert user2.get("/api/ratings").get_json() == {"ratings": {}}

    with app.app_context():
        db = get_db()
        user_id = db.execute("SELECT id FROM users WHERE email = ?", ("nimal@example.com",)).fetchone()["id"]
        assert db.execute("SELECT COUNT(*) FROM favourites WHERE user_id = ?", (user_id,)).fetchone()[0] == 1
        assert db.execute("SELECT stars FROM ratings WHERE user_id = ?", (user_id,)).fetchone()[0] == 4

    assert user.put("/api/ratings", json={**recipe, "stars": 0}).status_code == 200
    assert user.get("/api/ratings").get_json() == {"ratings": {}}
    assert user.delete("/api/favorites", json=recipe).get_json() == {"ok": True}
    assert user.get("/api/favorites").get_json() == {"favorites": []}


def test_meal_plan_persists_and_can_be_cleared(app, user):
    response = user.put("/api/meal-plan", json={"meals": [
        {"day": "Mon", "meal": "Breakfast", "recipe": {
            "name": "Backend Oatmeal", "ingredients": ["oats", "milk"]}},
        {"day": "Tue", "meal": "Dinner", "recipe": {
            "name": "Backend Soup", "ingredients": ["lentils"]}},
    ]})
    assert response.status_code == 200
    meals = response.get_json()["meals"]
    assert [(item["day"], item["meal"], item["recipe_name"]) for item in meals] == [
        ("Mon", "Breakfast", "Backend Oatmeal"),
        ("Tue", "Dinner", "Backend Soup"),
    ]

    assert user.get("/api/meal-plan").get_json() == {"meals": meals}
    assert user.put("/api/meal-plan", json={"meals": [
        {"day": "Mon", "meal": "Dinner", "recipe": None},
    ]}).get_json() == {"meals": []}

    response = user.put("/api/meal-plan", json={"meals": [
        {"day": "Mon", "meal": "Breakfast", "recipe": {"name": "A"}},
        {"day": "Mon", "meal": "Breakfast", "recipe": {"name": "B"}},
    ]})
    assert response.status_code == 400
    assert user.delete("/api/meal-plan").get_json() == {"ok": True}


def test_user_food_endpoints_require_login(client):
    for path in ("/api/favorites", "/api/ratings", "/api/meal-plan"):
        assert client.get(path).status_code == 401


def test_profile_and_pantry_writes_mirror_legacy_tables(app, user):
    response = user.put("/api/profile", json={
        "height": 170, "weight": 70, "target_weight": 65,
    })
    assert response.status_code == 200
    added = user.post("/api/pantry", json={
        "name": "Mirror Beans", "category": "Protein", "quantity": 2, "unit": "kg",
    })
    assert added.status_code == 201

    with app.app_context():
        db = get_db()
        health = db.execute(
            "SELECT height_cm, weight_kg, target_kg FROM health "
            "WHERE user_id = (SELECT id FROM users WHERE email = ?)",
            ("nimal@example.com",),
        ).fetchone()
        pantry = db.execute(
            "SELECT name, cat, qty, unit FROM pantry_items "
            "WHERE user_id = (SELECT id FROM users WHERE email = ?) AND name = ?",
            ("nimal@example.com", "Mirror Beans"),
        ).fetchone()
    assert tuple(health) == (170.0, 70.0, 65.0)
    assert tuple(pantry) == ("Mirror Beans", "Protein", 2.0, "kg")

    user.delete("/api/pantry", json={})
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM pantry_items").fetchone()[0] == 0
