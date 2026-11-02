from conftest import make_user


def test_profile_defaults_and_save(user):
    profile = user.get("/api/profile").get_json()
    assert profile == {
        "name": "Nimal",
        "age": None,
        "height": None,
        "weight": None,
        "allergies": [],
        "health_notes": "",
        "calorie_goal": None,
        "target_weight": None,
    }

    response = user.put("/api/profile", json={
        "name": "Nimal Perera",
        "age": 31,
        "height": 170,
        "weight": 72.5,
        "allergies": " Peanuts, eggs, PEANUTS ",
        "health_notes": "Avoid strenuous exercise",
        "calorie_goal": 2200,
        "target_weight": 68,
    })
    assert response.status_code == 200
    assert response.get_json() == {
        "name": "Nimal Perera",
        "age": 31,
        "height": 170,
        "weight": 72.5,
        "allergies": ["peanuts", "eggs"],
        "health_notes": "Avoid strenuous exercise",
        "calorie_goal": 2200,
        "target_weight": 68,
    }
    assert user.get("/api/profile").get_json()["weight"] == 72.5
    assert user.get("/api/me").get_json()["user"]["name"] == "Nimal Perera"


def test_profile_partial_update_and_clear(user):
    user.put("/api/profile", json={"height": 170, "weight": 70, "allergies": ["eggs"]})
    response = user.put("/api/profile", json={"allergies": [], "health_notes": ""})
    profile = response.get_json()
    assert profile["height"] == 170 and profile["weight"] == 70
    assert profile["allergies"] == [] and profile["health_notes"] == ""


def test_profile_validation(user):
    invalid = [
        {"age": 121},
        {"age": 2.5},
        {"height": 99},
        {"height": 231},
        {"weight": 24.9},
        {"weight": 251},
        {"calorie_goal": 999},
        {"calorie_goal": 4001},
        {"target_weight": 24},
        {"allergies": ["<script>"]},
        {"allergies": [42]},
        {"health_notes": "x" * 501},
    ]
    for data in invalid:
        assert user.put("/api/profile", json=data).status_code == 400, data
    assert user.put("/api/profile", json=[]).status_code == 400


def test_profile_requires_login_and_standard_error(client):
    response = client.get("/api/profile")
    assert response.status_code == 401
    assert response.get_json() == {"error": "Not logged in"}


def test_profile_is_private(app, user):
    other, _ = make_user(app, "Other User", "other@example.com")
    user.put("/api/profile", json={"weight": 75})
    assert other.get("/api/profile").get_json()["weight"] is None
