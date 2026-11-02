from datetime import date, timedelta


def add(c, **kw):
    kw.setdefault("name", "Rice")
    return c.post("/api/pantry", json=kw)


def items(c, today=None):
    url = "/api/pantry" + ("?today=" + today if today else "")
    return c.get(url).get_json()


def test_new_account_has_sample_pantry(user):
    data = items(user)
    assert data["summary"]["items"] == 4


def test_add_item_and_validation(user):
    r = add(user, name="Beans", cat="Vegetables", qty=0.5, unit="kg", exp="2030-01-31")
    assert r.status_code == 201 and r.get_json()["item"]["qty"] == 0.5
    for payload in [{"name": ""}, {"name": "   "}, {"name": "<b>x</b>"}, {"name": "A" * 61},
                    {"name": "X", "qty": 0}, {"name": "X", "qty": -2}, {"name": "X", "qty": "abc"},
                    {"name": "X", "unit": "bunches"}, {"name": "X", "cat": "Snacks"},
                    {"name": "X", "exp": "2026-02-30"}, {"name": "X", "exp": "tomorrow"}]:
        assert user.post("/api/pantry", json=payload).status_code == 400, payload


def test_blank_amount_defaults_to_one_not_zero(user):
    r = user.post("/api/pantry", json={"name": "Salt"})
    assert r.get_json()["item"]["qty"] == 1


def test_merge_same_name_and_unit(user):
    add(user, name="Onion", qty=10, unit="pcs", exp="2030-05-10")
    r = add(user, name="ONION", qty=2, unit="pcs", exp="2030-05-02")
    body = r.get_json()
    assert r.status_code == 200 and body["merged"] is True
    assert body["item"]["qty"] == 12 and body["item"]["exp"] == "2030-05-02"  # earlier expiry kept
    assert sum(1 for i in items(user)["items"] if i["name"].lower() == "onion") == 1


def test_different_unit_is_not_merged(user):
    add(user, name="Flour", qty=15, unit="pcs")
    r = add(user, name="Flour", qty=1, unit="kg")
    assert r.status_code == 201 and r.get_json()["merged"] is False


def test_edit_item(user):
    iid = add(user, name="Milk powder", qty=1, unit="kg").get_json()["item"]["id"]
    r = user.put("/api/pantry/%d" % iid, json={"qty": 2.5, "exp": "2031-01-01", "name": "Milk powder 1"})
    assert r.status_code == 200 and r.get_json()["item"]["qty"] == 2.5
    assert user.put("/api/pantry/%d" % iid, json={"qty": 0}).status_code == 400
    assert user.put("/api/pantry/99999", json={"qty": 1}).status_code == 404


def test_edit_cannot_create_duplicate(user):
    add(user, name="Tea", qty=1, unit="kg")
    iid = add(user, name="Coffee", qty=1, unit="kg").get_json()["item"]["id"]
    assert user.put("/api/pantry/%d" % iid, json={"name": "tea"}).status_code == 409


def test_quantity_buttons(user):
    iid = add(user, name="Lime", qty=2, unit="pcs").get_json()["item"]["id"]
    assert user.patch("/api/pantry/%d/quantity" % iid, json={"delta": 1}).get_json()["item"]["qty"] == 3
    assert user.patch("/api/pantry/%d/quantity" % iid, json={"delta": "x"}).status_code == 400
    user.patch("/api/pantry/%d/quantity" % iid, json={"delta": -2})
    r = user.patch("/api/pantry/%d/quantity" % iid, json={"delta": -1})
    assert r.get_json()["deleted"] is True  # reaching 0 removes it, never negative
    assert user.patch("/api/pantry/%d/quantity" % iid, json={"delta": 1}).status_code == 404


def test_delete_one_and_clear(user):
    iid = add(user, name="Pear").get_json()["item"]["id"]
    assert user.delete("/api/pantry/%d" % iid).status_code == 200
    assert user.delete("/api/pantry/%d" % iid).status_code == 404
    assert user.delete("/api/pantry").get_json()["removed"] >= 4
    assert items(user)["items"] == []


def test_expiry_state_uses_the_clients_date(user):
    today = date(2030, 6, 15)
    user.delete("/api/pantry")
    for label, delta in [("past", -1), ("now", 0), ("soon", 2), ("later", 10)]:
        add(user, name=label, exp=(today + timedelta(days=delta)).isoformat())
    add(user, name="noexp")
    got = {i["name"]: (i["state"], i["days_left"]) for i in items(user, today.isoformat())["items"]}
    assert got == {"past": ("expired", -1), "now": ("today", 0), "soon": ("soon", 2),
                   "later": ("ok", 10), "noexp": ("none", None)}
    s = items(user, today.isoformat())["summary"]
    assert s["use_soon"] == 2 and s["expired"] == 1   # expired items are not counted as "use soon"


def test_pantry_is_private_per_account(user, user2):
    iid = add(user, name="SecretSpice").get_json()["item"]["id"]
    assert all(i["name"] != "SecretSpice" for i in items(user2)["items"])
    assert user2.put("/api/pantry/%d" % iid, json={"qty": 9}).status_code == 404
    assert user2.delete("/api/pantry/%d" % iid).status_code == 404
    assert user2.patch("/api/pantry/%d/quantity" % iid, json={"delta": 1}).status_code == 404
    user2.delete("/api/pantry")
    assert any(i["name"] == "SecretSpice" for i in items(user)["items"])
