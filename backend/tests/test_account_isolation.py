from conftest import make_user


def test_logout_and_login_switches_between_isolated_accounts(app):
    account_a, _ = make_user(app, "Account A", "account-a@example.com")
    account_b, _ = make_user(app, "Account B", "account-b@example.com")
    account_a.post("/api/pantry", json={
        "name": "A-only pantry", "category": "Vegetables", "quantity": 2, "unit": "pcs",
    })
    account_a.post("/api/shopping", json={"name": "A-only shopping"})

    account_a.post("/api/logout")
    login_b = account_a.post("/api/login", json={
        "email": "account-b@example.com", "password": "secret123",
    })
    assert login_b.status_code == 200
    assert all(
        item["name"] != "A-only pantry"
        for item in account_a.get("/api/pantry").get_json()["items"]
    )
    assert all(
        item["name"] != "A-only shopping"
        for item in account_a.get("/api/shopping").get_json()["items"]
    )
    account_a.post("/api/pantry", json={
        "name": "B-only pantry", "category": "Fruits", "quantity": 1, "unit": "pcs",
    })
    account_a.post("/api/shopping", json={"name": "B-only shopping"})

    account_a.post("/api/logout")
    login_a = account_a.post("/api/login", json={
        "email": "account-a@example.com", "password": "secret123",
    })
    assert login_a.status_code == 200
    assert any(item["name"] == "A-only pantry" for item in account_a.get("/api/pantry").get_json()["items"])
    assert any(item["name"] == "A-only shopping" for item in account_a.get("/api/shopping").get_json()["items"])
    assert all(item["name"] != "B-only pantry" for item in account_a.get("/api/pantry").get_json()["items"])
    assert all(item["name"] != "B-only shopping" for item in account_a.get("/api/shopping").get_json()["items"])
    assert any(item["name"] == "B-only pantry" for item in account_b.get("/api/pantry").get_json()["items"])
    assert any(item["name"] == "B-only shopping" for item in account_b.get("/api/shopping").get_json()["items"])


def test_account_data_is_isolated_across_user_features(app, user, user2):
    pantry_response = user.post("/api/pantry", json={
        "name": "Account A pantry item", "category": "Grains", "quantity": 2, "unit": "kg",
    })
    shopping_response = user.post("/api/shopping", json={
        "name": "Account A shopping item", "quantity": 3, "unit": "pcs",
    })
    assert pantry_response.status_code == 201
    assert shopping_response.status_code == 201
    pantry_id = pantry_response.get_json()["item"]["id"]
    shopping_id = shopping_response.get_json()["item"]["id"]

    user.put("/api/profile", json={"weight": 72})
    user.put("/api/dietary", json={"diets": ["Vegan"]})
    user.put("/api/meal-plan", json={"meals": [{
        "day": "Mon",
        "meal": "Breakfast",
        "recipe": {"name": "Account A private plan recipe", "ingredients": ["oats"]},
    }]})
    user.post("/api/favorites", json={"name": "Account A favorite"})
    user.put("/api/ratings", json={"name": "Account A rating", "stars": 5})
    user.put("/api/water", json={"day": "2026-11-05", "glasses": 6})

    assert all(
        item["name"] != "Account A pantry item"
        for item in user2.get("/api/pantry").get_json()["items"]
    )
    assert all(
        item["name"] != "Account A shopping item"
        for item in user2.get("/api/shopping").get_json()["items"]
    )
    assert user2.get("/api/profile").get_json()["weight"] is None
    assert user2.get("/api/dietary").get_json()["diets"] == []
    assert user2.get("/api/meal-plan").get_json()["meals"] == []
    assert user2.get("/api/favorites").get_json()["favorites"] == []
    assert user2.get("/api/ratings").get_json()["ratings"] == {}
    assert user2.get("/api/water?day=2026-11-05").get_json()["glasses"] == 0

    assert user2.put("/api/shopping", json={"items": [{
        "name": "Account B item", "user_id": 1,
    }]}).status_code == 200
    assert user2.put("/api/profile", json={"weight": 80, "user_id": 1}).status_code == 200
    assert user2.patch(f"/api/shopping/{shopping_id}", json={"is_bought": True}).status_code == 404
    assert user2.delete(f"/api/shopping/{shopping_id}").status_code == 404
    assert user2.get(f"/api/pantry/{pantry_id}").status_code == 404
    assert user2.put(f"/api/pantry/{pantry_id}", json={"quantity": 20}).status_code == 404
    assert user2.delete(f"/api/pantry/{pantry_id}").status_code == 404

    assert any(
        item["name"] == "Account A pantry item"
        for item in user.get("/api/pantry").get_json()["items"]
    )
    assert any(
        item["name"] == "Account A shopping item"
        for item in user.get("/api/shopping").get_json()["items"]
    )
    assert user.get("/api/profile").get_json()["weight"] == 72
    assert user.get("/api/dietary").get_json()["diets"] == ["Vegan"]
    assert user.get("/api/meal-plan").get_json()["meals"][0]["recipe_name"] == (
        "Account A private plan recipe"
    )
    assert user.get("/api/favorites").get_json()["favorites"] == ["Account A favorite"]
    assert user.get("/api/ratings").get_json()["ratings"] == {"Account A rating": 5}
    assert user.get("/api/water?day=2026-11-05").get_json()["glasses"] == 6

    reset = user2.delete("/api/account/data", json={"confirm": True})
    assert reset.status_code == 200
    assert any(
        item["name"] == "Account A pantry item"
        for item in user.get("/api/pantry").get_json()["items"]
    )
    assert any(
        item["name"] == "Account A shopping item"
        for item in user.get("/api/shopping").get_json()["items"]
    )
    assert user.get("/api/favorites").get_json()["favorites"] == ["Account A favorite"]
    assert user.get("/api/meal-plan").get_json()["meals"][0]["recipe_name"] == (
        "Account A private plan recipe"
    )
