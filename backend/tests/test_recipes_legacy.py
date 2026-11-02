import io

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def test_recipes_seeded_and_listed(user):
    r = user.get("/api/recipes").get_json()
    assert len(r) == 7 and set(r[0]) == {"id", "name", "ingredients", "instructions", "image"}


def test_add_recipe_persists(user):
    form = {"name": "Dhal soup", "ingredients": "dhal, onion", "instructions": "Boil.", "imageFile": (io.BytesIO(PNG), "d.png")}
    r = user.post("/api/recipes", data=form, content_type="multipart/form-data")
    assert r.status_code == 201 and r.get_json()["recipe"]["id"] == 8 and r.get_json()["success"] is True
    assert len(user.get("/api/recipes").get_json()) == 8


def test_add_recipe_rejects_missing_and_fake_photo(user):
    base = {"name": "X", "ingredients": "a", "instructions": "b"}
    assert user.post("/api/recipes", data=dict(base, name=""), content_type="multipart/form-data").status_code == 400
    ok = user.post("/api/recipes", data=base, content_type="multipart/form-data")  # photo is optional
    assert ok.status_code == 201 and ok.get_json()["recipe"]["image"] == ""
    bad = dict(base, imageFile=(io.BytesIO(b"text"), "x.png"))
    assert user.post("/api/recipes", data=bad, content_type="multipart/form-data").status_code == 415


def test_recipe_list_is_public(client):
    assert client.get("/api/recipes").status_code == 200


def test_old_recipes_json_is_imported_once(tmp_path):
    import json
    from app import create_app
    p = tmp_path / "recipes.json"
    p.write_text(json.dumps([{"id": 8, "name": "Old saved", "ingredients": ["a"], "instructions": "b", "image": ""}]))
    from db import init_db, import_recipes_json
    dbp = str(tmp_path / "x.db")
    init_db(dbp); import_recipes_json(dbp, str(p)); import_recipes_json(dbp, str(p))
    import sqlite3
    assert sqlite3.connect(dbp).execute("SELECT COUNT(*) FROM recipes WHERE name='Old saved'").fetchone()[0] == 1
