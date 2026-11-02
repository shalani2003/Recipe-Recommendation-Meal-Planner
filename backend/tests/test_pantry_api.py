"""
Tests for the pantry API.

Run from the backend folder:
    python -m unittest discover -s tests -v
They use a temporary database, so vitaplate.db is never touched.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

# Must be set before app.py is imported.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["VITAPLATE_DB"] = _tmp.name
os.environ["SECRET_KEY"] = "test-secret-key"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as vitaplate  # noqa: E402


def tearDownModule():
    os.unlink(_tmp.name)


class PantryApiTests(unittest.TestCase):
    def setUp(self):
        with sqlite3.connect(_tmp.name) as db:
            db.execute("DELETE FROM pantry_items")
            db.execute("DELETE FROM users")
        vitaplate.app.config["TESTING"] = True
        self.alice = self.new_user("alice@example.com")
        self.bob = self.new_user("bob@example.com")

    def new_user(self, email):
        client = vitaplate.app.test_client()
        res = client.post(
            "/api/register", json={"name": "Test User", "email": email, "password": "password1"}
        )
        self.assertEqual(res.status_code, 201)
        return client

    def add(self, client=None, **fields):
        client = client or self.alice
        payload = {"name": "Rice", "quantity": 2, "unit": "kg", "category": "Grains"}
        payload.update(fields)
        return client.post("/api/pantry", json=payload)

    # ---------------------------------------------------------- login rules
    def test_every_route_requires_login(self):
        anon = vitaplate.app.test_client()
        calls = [
            anon.get("/api/pantry"),
            anon.post("/api/pantry", json={"name": "Rice"}),
            anon.put("/api/pantry/1", json={"quantity": 3}),
            anon.delete("/api/pantry/1"),
            anon.delete("/api/pantry"),
            anon.post("/api/pantry/import", json={"items": []}),
        ]
        for res in calls:
            self.assertEqual(res.status_code, 401)

    def test_session_of_a_deleted_user_is_rejected(self):
        with sqlite3.connect(_tmp.name) as db:
            db.execute("DELETE FROM users WHERE email = 'alice@example.com'")
        self.assertEqual(self.alice.get("/api/pantry").status_code, 401)

    # ------------------------------------------------------------- add/list
    def test_add_and_list(self):
        res = self.add(expiry_date="2026-12-31")
        self.assertEqual(res.status_code, 201)
        item = res.get_json()["item"]
        self.assertEqual(
            {k: item[k] for k in ("name", "category", "quantity", "unit", "expiry_date")},
            {"name": "Rice", "category": "Grains", "quantity": 2, "unit": "kg", "expiry_date": "2026-12-31"},
        )
        self.assertFalse(res.get_json()["merged"])

        data = self.alice.get("/api/pantry").get_json()
        self.assertEqual([i["name"] for i in data["items"]], ["Rice"])
        self.assertIsInstance(data["user_id"], int)

    def test_defaults(self):
        item = self.alice.post("/api/pantry", json={"name": "  Red   onions "}).get_json()["item"]
        self.assertEqual(item["name"], "Red onions")
        self.assertEqual((item["category"], item["quantity"], item["unit"], item["expiry_date"]), ("Other", 1, "pcs", None))

    def test_same_name_is_merged(self):
        self.add(quantity=2, expiry_date="2026-12-31")
        res = self.add(name="rice", quantity=3, expiry_date="2026-11-01")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["merged"])
        self.assertEqual(body["item"]["quantity"], 5)
        self.assertEqual(body["item"]["expiry_date"], "2026-11-01")  # the earlier date is kept
        self.assertEqual(len(self.alice.get("/api/pantry").get_json()["items"]), 1)

    def test_same_name_with_other_unit_is_a_conflict(self):
        self.add(unit="kg")
        res = self.add(unit="pcs")
        self.assertEqual(res.status_code, 409)
        self.assertIn("already in your pantry", res.get_json()["error"])

    def test_validation(self):
        bad = [
            {"name": ""},
            {"name": "x" * 81},
            {"quantity": 0},
            {"quantity": -2},
            {"quantity": "abc"},
            {"quantity": "nan"},
            {"quantity": 10**9},
            {"quantity": True},
            {"unit": "gallons"},
            {"category": "Candy"},
            {"expiry_date": "2026-02-30"},
            {"expiry_date": "31/12/2026"},
        ]
        for fields in bad:
            with self.subTest(fields=fields):
                self.assertEqual(self.add(**fields).status_code, 400)
        self.assertEqual(self.alice.get("/api/pantry").get_json()["items"], [])

    def test_non_json_body_is_rejected(self):
        res = self.alice.post("/api/pantry", data="name=Rice", content_type="text/plain")
        self.assertEqual(res.status_code, 400)

    # ----------------------------------------------------------------- edit
    def test_edit_every_field(self):
        item_id = self.add(expiry_date="2026-12-31").get_json()["item"]["id"]
        res = self.alice.put(
            f"/api/pantry/{item_id}",
            json={"name": "Basmati rice", "category": "Grains", "quantity": 4.5, "unit": "g", "expiry_date": None},
        )
        self.assertEqual(res.status_code, 200)
        item = res.get_json()["item"]
        self.assertEqual((item["name"], item["quantity"], item["unit"], item["expiry_date"]), ("Basmati rice", 4.5, "g", None))

    def test_partial_edit_keeps_other_fields(self):
        item_id = self.add().get_json()["item"]["id"]
        item = self.alice.patch(f"/api/pantry/{item_id}", json={"quantity": 7}).get_json()["item"]
        self.assertEqual((item["name"], item["quantity"], item["unit"]), ("Rice", 7, "kg"))

    def test_edit_errors(self):
        first = self.add(name="Rice").get_json()["item"]["id"]
        self.add(name="Dhal", quantity=1, unit="kg")
        self.assertEqual(self.alice.put(f"/api/pantry/{first}", json={"name": "dhal"}).status_code, 409)
        self.assertEqual(self.alice.put(f"/api/pantry/{first}", json={}).status_code, 400)
        self.assertEqual(self.alice.put(f"/api/pantry/{first}", json={"quantity": 0}).status_code, 400)
        self.assertEqual(self.alice.put("/api/pantry/99999", json={"quantity": 1}).status_code, 404)

    # --------------------------------------------------------------- delete
    def test_delete_one_and_clear_all(self):
        a = self.add(name="Rice").get_json()["item"]["id"]
        self.add(name="Dhal")
        self.add(name="Eggs", unit="pcs")
        self.assertEqual(self.alice.delete(f"/api/pantry/{a}").status_code, 200)
        self.assertEqual(self.alice.delete(f"/api/pantry/{a}").status_code, 404)
        res = self.alice.delete("/api/pantry")
        self.assertEqual(res.get_json(), {"ok": True, "deleted": 2})
        self.assertEqual(self.alice.get("/api/pantry").get_json()["items"], [])

    # ------------------------------------------------------ users are apart
    def test_users_cannot_see_or_change_each_others_items(self):
        item_id = self.add(name="Rice").get_json()["item"]["id"]
        self.assertEqual(self.bob.get("/api/pantry").get_json()["items"], [])
        self.assertEqual(self.bob.put(f"/api/pantry/{item_id}", json={"quantity": 99}).status_code, 404)
        self.assertEqual(self.bob.delete(f"/api/pantry/{item_id}").status_code, 404)
        self.assertEqual(self.bob.delete("/api/pantry").get_json()["deleted"], 0)
        # Bob can have his own "Rice" and Alice's is untouched.
        self.assertEqual(self.add(self.bob, name="Rice", quantity=1).status_code, 201)
        alice_rice = self.alice.get("/api/pantry").get_json()["items"][0]
        self.assertEqual(alice_rice["quantity"], 2)

    # --------------------------------------------------------------- import
    def test_import_maps_old_categories_and_skips_bad_rows(self):
        self.add(name="Eggs", quantity=2, unit="pcs", category="Protein")
        res = self.alice.post(
            "/api/pantry/import",
            json={
                "items": [
                    {"name": "Carrot", "category": "Produce", "quantity": 3, "unit": "pcs"},
                    {"name": "Flour", "category": "Pantry", "quantity": 1, "unit": "kg"},
                    {"name": "Curry powder", "category": "Spices & Oils", "quantity": 1, "unit": "pcs"},
                    {"name": "Weird", "category": "???", "quantity": 1, "unit": "bags", "expiry_date": "nope"},
                    {"name": "eggs", "quantity": 4, "unit": "pcs"},   # merges into Eggs
                    {"name": "", "quantity": 1},                       # skipped: no name
                    {"name": "Bad qty", "quantity": 0},                # skipped: bad quantity
                    "not an object",                                   # skipped
                ]
            },
        )
        self.assertEqual(res.get_json(), {"imported": 4, "merged": 1, "skipped": 3})
        items = {i["name"]: i for i in self.alice.get("/api/pantry").get_json()["items"]}
        self.assertEqual(items["Carrot"]["category"], "Vegetables")
        self.assertEqual(items["Flour"]["category"], "Grains")
        self.assertEqual(items["Curry powder"]["category"], "Spices & sauces")
        self.assertEqual((items["Weird"]["category"], items["Weird"]["unit"], items["Weird"]["expiry_date"]), ("Other", "pcs", None))
        self.assertEqual(items["Eggs"]["quantity"], 6)

    def test_import_bad_payloads(self):
        self.assertEqual(self.alice.post("/api/pantry/import", json={"items": "x"}).status_code, 400)
        self.assertEqual(self.alice.post("/api/pantry/import", json={}).status_code, 400)
        too_many = [{"name": f"Item {i}"} for i in range(501)]
        self.assertEqual(self.alice.post("/api/pantry/import", json={"items": too_many}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
