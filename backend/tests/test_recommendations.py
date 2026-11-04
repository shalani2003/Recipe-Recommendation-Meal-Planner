def test_recommendations_are_ranked_from_user_data(user):
    user.post("/api/pantry", json={"name": "chickpeas"})
    user.post("/api/pantry", json={"name": "tomato"})

    response = user.get("/api/recommendations")

    assert response.status_code == 200
    recipes = response.get_json()["recommendations"]
    assert recipes[0]["name"] == "Chickpea Salad Bowl"
    assert recipes[0]["pantry_match"] == 50
    assert all("ingredients" in recipe for recipe in recipes)


def test_recommendations_require_a_session(client):
    assert client.get("/api/recommendations").status_code == 401
