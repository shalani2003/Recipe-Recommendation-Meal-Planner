import io

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 40


def test_dietary_defaults_and_save(user):
    assert user.get("/api/dietary").get_json() == {"diets": [], "allergies": [], "onboarding_completed": False}
    r = user.put("/api/dietary", json={"diets": ["Vegan", "Halal"], "allergies": [" Eggs ", "eggs", "Peanuts"]})
    assert r.get_json() == {"diets": ["Vegan", "Halal"], "allergies": ["eggs", "peanuts"], "onboarding_completed": False}
    assert user.get("/api/profile").get_json()["allergies"] == ["eggs", "peanuts"]
    user.put("/api/dietary", json={"onboarding_completed": True})
    got = user.get("/api/dietary").get_json()
    assert got["diets"] == ["Vegan", "Halal"] and got["onboarding_completed"] is True  # partial update keeps the rest
    user.put("/api/dietary", json={"diets": []})  # deselect works
    assert user.get("/api/dietary").get_json()["diets"] == []


def test_profile_and_dietary_allergies_stay_in_sync(user):
    user.put("/api/profile", json={"allergies": "eggs, peanuts"})
    assert user.get("/api/dietary").get_json()["allergies"] == ["eggs", "peanuts"]


def test_dietary_validation(user):
    assert user.put("/api/dietary", json={"diets": ["Carnivore"]}).status_code == 400
    assert user.put("/api/dietary", json={"diets": "Vegan"}).status_code == 400
    assert user.put("/api/dietary", json={"allergies": ["<script>"]}).status_code == 400
    assert user.put("/api/dietary", json={"allergies": ["x"] * 0 + ["a%d" % i for i in range(25)]}).status_code == 400
    assert user.put("/api/dietary", json={"onboarding_completed": "false"}).status_code == 400
    assert user.put("/api/dietary", json=[]).status_code == 400


def test_dietary_is_private(user, user2):
    user.put("/api/dietary", json={"diets": ["Vegan"], "allergies": ["eggs"]})
    assert user2.get("/api/dietary").get_json()["diets"] == []


def test_settings_read_and_update(user):
    s = user.get("/api/settings").get_json()
    assert s["name"] == "Nimal" and s["preferences"]["notificationMode"] == "all" and s["picture_url"] is None
    r = user.put("/api/settings", json={"name": "Nimal P", "email": "NEW@example.com",
                                        "preferences": {"notificationMode": "off", "mealReminders": False}})
    got = r.get_json()
    assert got["name"] == "Nimal P" and got["email"] == "new@example.com"
    assert got["preferences"] == {"notificationMode": "off", "mealReminders": False, "weeklySummary": True}
    assert user.get("/api/me").get_json()["user"]["name"] == "Nimal P"  # one place for the name


def test_settings_validation_and_email_clash(app, user, user2):
    assert user.put("/api/settings", json={"email": "kamala@example.com"}).status_code == 409
    assert user.put("/api/settings", json={"email": "bad"}).status_code == 400
    assert user.put("/api/settings", json={"name": "A"}).status_code == 400
    assert user.put("/api/settings", json={"preferences": {"notificationMode": "loud"}}).status_code == 400
    assert user.put("/api/settings", json={"preferences": {"mealReminders": "yes"}}).status_code == 400


def test_change_password(user, app):
    assert user.post("/api/settings/password", json={"current_password": "nope12345", "new_password": "fresh1234"}).status_code == 403
    assert user.post("/api/settings/password", json={"current_password": "secret123", "new_password": "short"}).status_code == 400
    assert user.post("/api/settings/password", json={"current_password": "secret123", "new_password": "secret123"}).status_code == 400
    assert user.post("/api/settings/password", json={"current_password": "secret123", "new_password": "fresh1234"}).status_code == 200
    fresh = app.test_client()
    assert fresh.post("/api/login", json={"email": "nimal@example.com", "password": "fresh1234"}).status_code == 200
    assert fresh.post("/api/login", json={"email": "nimal@example.com", "password": "secret123"}).status_code == 401


def test_new_recovery_code(user):
    assert user.post("/api/settings/recovery-code", json={"password": "wrong"}).status_code == 403
    assert len(user.post("/api/settings/recovery-code", json={"password": "secret123"}).get_json()["recovery_code"]) == 14


def upload(c, data, name="me.png", field="picture"):
    return c.post("/api/settings/picture", data={field: (io.BytesIO(data), name)}, content_type="multipart/form-data")


def test_picture_upload_show_replace_delete(user):
    r = upload(user, PNG)
    assert r.status_code == 201
    assert user.get("/api/settings").get_json()["picture_url"].startswith("/api/settings/picture")
    assert user.get("/api/settings/picture").data == PNG
    assert upload(user, JPG, "me.jpg").status_code == 201          # replace
    assert user.get("/api/settings/picture").data == JPG
    assert user.delete("/api/settings/picture").status_code == 200
    assert user.get("/api/settings/picture").status_code == 404


def test_picture_rejects_fake_wrong_big_and_missing(user):
    assert upload(user, b"this is just text").status_code == 415            # text renamed .png
    assert upload(user, PNG, "x.txt").status_code == 201                      # real bytes win over the name
    assert upload(user, PNG + b"0" * (2 * 1024 * 1024)).status_code == 413
    assert user.post("/api/settings/picture", data={}, content_type="multipart/form-data").status_code == 400


def test_picture_is_private(user, user2):
    upload(user, PNG)
    assert user2.get("/api/settings/picture").status_code == 404


def test_reset_all_data_keeps_login(app, user):
    user.put("/api/dietary", json={"diets": ["Vegan"]})
    upload(user, PNG)
    assert user.delete("/api/account/data", json={}).status_code == 400    # needs confirm
    r = user.delete("/api/account/data", json={"confirm": True}).get_json()
    assert r["account_kept"] is True
    assert user.get("/api/pantry").get_json()["items"] == []
    assert user.get("/api/dietary").get_json()["diets"] == []
    assert user.get("/api/settings").get_json()["picture_url"] is None
    assert user.get("/api/me").status_code == 200                             # still logged in
    assert app.test_client().post("/api/login", json={"email": "nimal@example.com", "password": "secret123"}).status_code == 200


def test_reset_all_data_only_touches_own_data(user, user2):
    user.delete("/api/account/data", json={"confirm": True})
    assert len(user2.get("/api/pantry").get_json()["items"]) == 4
