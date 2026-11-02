"""
Tests for the recipes, favourites and ratings API.

Run from the backend folder:
    python -m unittest discover -s tests -v
"""
import io
import os
import sqlite3
import unittest

try:
    from . import support
except ImportError:  # started with: python -m unittest discover -s tests
    import support

vitaplate = support.vitaplate

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 32


class RecipesApiTests(unittest.TestCase):
    def setUp(self):
        with sqlite3.connect(support.DB_PATH) as db:
            db.execute("DELETE FROM users")
            db.execute("DELETE FROM favorites")
            db.execute("DELETE FROM ratings")
            for (recipe_id,) in db.execute("SELECT id FROM recipes WHERE id > 15").fetchall():
                db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
                db.execute("DELETE FROM recipe_diets WHERE recipe_id = ?", (recipe_id,))
                db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        for name in os.listdir(support.UPLOAD_DIR):
            os.unlink(os.path.join(support.UPLOAD_DIR, name))
        vitaplate.app.config["TESTING"] = True
        self.alice = self.new_user("alice@example.com")
        self.bob = self.new_user("bob@example.com")

    def new_user(self, email):
        client = vitaplate.app.test_client()
        res = client.post("/api/register", json={"name": "Test User", "email": email, "password": "password1"})
        self.assertEqual(res.status_code, 201)
        return client

    def recipes(self, client=None, query=""):
        res = (client or self.alice).get("/api/recipes" + query)
        self.assertEqual(res.status_code, 200)
        return res.get_json()["recipes"]

    def recipe(self, recipe_id, client=None):
        return (client or self.alice).get(f"/api/recipes/{recipe_id}").get_json()["recipe"]

    def create(self, client=None, image=(PNG, "dish.png"), **overrides):
        data = {
            "name": "Vegetable Rice Bowl 2",
            "ingredients": "rice, carrot, peas",
            "instructions": "Cook and serve.",
        }
        data.update(overrides)
        data = {k: v for k, v in data.items() if v is not None}
        if image is not None:
            data["imageFile"] = (io.BytesIO(image[0]), image[1])
        return (client or self.alice).post("/api/recipes", data=data, content_type="multipart/form-data")

    def uploaded_files(self):
        return os.listdir(support.UPLOAD_DIR)

    # ---------------------------------------------------------- login rules
    def test_every_route_requires_login(self):
        anon = vitaplate.app.test_client()
        calls = [
            anon.get("/api/recipes"),
            anon.get("/api/recipes/1"),
            anon.post("/api/recipes", data={"name": "x"}),
            anon.put("/api/recipes/1/favorite"),
            anon.delete("/api/recipes/1/favorite"),
            anon.get("/api/favorites"),
            anon.post("/api/favorites/import", json={"recipe_ids": []}),
            anon.put("/api/recipes/1/rating", json={"stars": 3}),
            anon.delete("/api/recipes/1/rating"),
            anon.post("/api/ratings/import", json={"ratings": {}}),
        ]
        for res in calls:
            self.assertEqual(res.status_code, 401)

    # -------------------------------------------------------------- catalogue
    def test_starter_recipes_are_in_the_database(self):
        recipes = self.recipes()
        self.assertEqual([r["id"] for r in recipes], list(range(1, 16)))
        first = recipes[0]
        self.assertEqual(first["name"], "Chicken & broccoli bowl")
        self.assertEqual((first["time"], first["kcal"], first["protein"], first["carbs"], first["fat"]), (25, 480, 38, 40, 16))
        self.assertEqual(first["ingredients"], ["Chicken", "Broccoli", "Rice"])
        self.assertEqual(first["diets"], ["Dairy-free", "Gluten-free", "Halal"])
        self.assertTrue(first["image"].startswith("assets/food/"))
        self.assertEqual((first["avg_rating"], first["rating_count"], first["my_rating"], first["is_favorite"]), (None, 0, 0, False))
        old_node_recipe = recipes[8]
        self.assertEqual(old_node_recipe["name"], "Chickpea Salad Bowl")
        self.assertIsNone(old_node_recipe["kcal"])
        self.assertEqual(old_node_recipe["ingredients"], ["chickpeas", "cucumber", "tomato", "lemon"])

    def test_get_one_recipe(self):
        self.assertEqual(self.recipe(2)["name"], "Pumpkin dhal curry")
        self.assertEqual(self.alice.get("/api/recipes/9999").status_code, 404)

    def test_search_by_name_and_ingredient(self):
        names = lambda q: [r["name"] for r in self.recipes(query=q)]  # noqa: E731
        self.assertEqual(names("?q=omelette"), ["Tomato omelette", "Spinach Omelette"])
        self.assertIn("Egg fried rice", names("?q=EGGS"))                      # ingredient, any case
        self.assertIn("Baked Salmon with Vegetables", names("?q=olive"))       # ingredient only
        self.assertEqual(names("?q=zzz-no-such-thing"), [])
        self.assertEqual(len(names("?q=")), 15)

    def test_diet_filter_needs_every_tag(self):
        vegan = [r["name"] for r in self.recipes(query="?diet=Vegan")]
        self.assertIn("Pumpkin dhal curry", vegan)
        self.assertNotIn("Egg fried rice", vegan)
        both = [r["name"] for r in self.recipes(query="?diet=vegan&diet=Gluten-free")]
        self.assertIn("Pumpkin dhal curry", both)
        self.assertNotIn("Avocado toast", both)   # vegan but not tagged gluten-free
        self.assertEqual(self.alice.get("/api/recipes?diet=Paleo").status_code, 400)
        self.assertEqual([r["name"] for r in self.recipes(query="?q=curry&diet=Halal")][:1], ["Pumpkin dhal curry"])

    # -------------------------------------------------------------- favourites
    def test_favourites(self):
        self.assertEqual(self.alice.put("/api/recipes/3/favorite").get_json(), {"is_favorite": True})
        self.assertEqual(self.alice.put("/api/recipes/3/favorite").status_code, 200)   # repeating is harmless
        self.alice.put("/api/recipes/5/favorite")
        self.assertTrue(self.recipe(3)["is_favorite"])
        self.assertEqual([r["id"] for r in self.alice.get("/api/favorites").get_json()["recipes"]], [3, 5])
        self.assertEqual(self.alice.delete("/api/recipes/3/favorite").get_json(), {"is_favorite": False})
        self.assertEqual(self.alice.delete("/api/recipes/3/favorite").status_code, 200)
        self.assertEqual([r["id"] for r in self.alice.get("/api/favorites").get_json()["recipes"]], [5])
        self.assertEqual(self.alice.put("/api/recipes/9999/favorite").status_code, 404)
        self.assertEqual(self.alice.delete("/api/recipes/9999/favorite").status_code, 404)

    def test_favourites_are_per_user(self):
        self.alice.put("/api/recipes/3/favorite")
        self.assertEqual(self.bob.get("/api/favorites").get_json()["recipes"], [])
        self.assertFalse(self.recipe(3, self.bob)["is_favorite"])

    def test_import_favourites_skips_unknown_ids(self):
        res = self.alice.post("/api/favorites/import", json={"recipe_ids": [1, 2, 2, 9999, "x", True, None]})
        self.assertEqual(res.get_json(), {"imported": 2})
        self.assertEqual([r["id"] for r in self.alice.get("/api/favorites").get_json()["recipes"]], [1, 2])
        self.assertEqual(self.alice.post("/api/favorites/import", json={"recipe_ids": "1"}).status_code, 400)

    # ----------------------------------------------------------------- ratings
    def test_rating_and_average(self):
        res = self.alice.put("/api/recipes/4/rating", json={"stars": 5})
        self.assertEqual(res.get_json(), {"avg_rating": 5.0, "rating_count": 1, "my_rating": 5})
        res = self.bob.put("/api/recipes/4/rating", json={"stars": 2})
        self.assertEqual(res.get_json(), {"avg_rating": 3.5, "rating_count": 2, "my_rating": 2})
        res = self.alice.put("/api/recipes/4/rating", json={"stars": 4})     # change my rating
        self.assertEqual(res.get_json(), {"avg_rating": 3.0, "rating_count": 2, "my_rating": 4})
        shown = self.recipe(4)
        self.assertEqual((shown["avg_rating"], shown["rating_count"], shown["my_rating"]), (3.0, 2, 4))
        self.assertEqual(self.recipe(4, self.bob)["my_rating"], 2)
        res = self.alice.delete("/api/recipes/4/rating")
        self.assertEqual(res.get_json(), {"avg_rating": 2.0, "rating_count": 1, "my_rating": 0})

    def test_rating_validation(self):
        for payload in ({"stars": 0}, {"stars": 6}, {"stars": "4"}, {"stars": 4.5}, {"stars": True}, {"stars": None}, {}):
            with self.subTest(payload=payload):
                self.assertEqual(self.alice.put("/api/recipes/4/rating", json=payload).status_code, 400)
        self.assertEqual(self.alice.put("/api/recipes/9999/rating", json={"stars": 3}).status_code, 404)
        self.assertEqual(self.alice.delete("/api/recipes/9999/rating").status_code, 404)
        self.assertEqual(self.recipe(4)["rating_count"], 0)

    def test_import_ratings_keeps_existing_ones(self):
        self.alice.put("/api/recipes/1/rating", json={"stars": 5})
        res = self.alice.post(
            "/api/ratings/import", json={"ratings": {"1": 2, "2": 4, "9999": 3, "abc": 3, "3": 9, "4": "5", "5": True}}
        )
        self.assertEqual(res.get_json(), {"imported": 1})
        self.assertEqual(self.recipe(1)["my_rating"], 5)   # not overwritten
        self.assertEqual(self.recipe(2)["my_rating"], 4)
        self.assertEqual(self.alice.post("/api/ratings/import", json={"ratings": []}).status_code, 400)

    # ------------------------------------------------------------- add recipe
    def test_add_recipe(self):
        res = self.create(
            name="  Pol   sambol  ", ingredients="coconut, Onion , coconut,,chilli", instructions=" Mix it. ",
            time="15", kcal="210", protein="3.5", carbs="12", fat="18", diet=["Vegan", "halal", "Vegan"],
        )
        self.assertEqual(res.status_code, 201)
        recipe = res.get_json()["recipe"]
        self.assertEqual(recipe["name"], "Pol sambol")
        self.assertEqual(recipe["ingredients"], ["coconut", "Onion", "chilli"])   # trimmed, no repeats
        self.assertEqual(recipe["instructions"], "Mix it.")
        self.assertEqual((recipe["time"], recipe["kcal"], recipe["protein"], recipe["carbs"], recipe["fat"]), (15, 210, 3.5, 12, 18))
        self.assertEqual(recipe["diets"], ["Halal", "Vegan"])
        self.assertTrue(recipe["image"].startswith("assets/food/recipe-") and recipe["image"].endswith(".png"))
        self.assertEqual(self.uploaded_files(), [recipe["image"].split("/")[-1]])
        with open(os.path.join(support.UPLOAD_DIR, self.uploaded_files()[0]), "rb") as handle:
            self.assertEqual(handle.read(), PNG)
        # everybody can see it, and it can be favourited and rated like the others
        self.assertEqual(self.recipe(recipe["id"], self.bob)["name"], "Pol sambol")
        self.assertEqual(self.bob.put(f"/api/recipes/{recipe['id']}/favorite").status_code, 200)
        self.assertEqual(self.bob.put(f"/api/recipes/{recipe['id']}/rating", json={"stars": 4}).status_code, 200)
        self.assertEqual(len(self.recipes()), 16)

    def test_add_recipe_with_only_required_fields(self):
        recipe = self.create().get_json()["recipe"]
        self.assertEqual((recipe["time"], recipe["kcal"], recipe["protein"], recipe["diets"]), (None, None, None, []))

    def test_photo_type_is_checked_by_content(self):
        for content, name, ext in ((JPEG, "a.jpeg", ".jpg"), (WEBP, "b.webp", ".webp"), (PNG, "wrong-name.txt", ".png")):
            with self.subTest(name=name):
                res = self.create(image=(content, name))
                self.assertEqual(res.status_code, 201)
                self.assertTrue(res.get_json()["recipe"]["image"].endswith(ext))
        before = len(self.uploaded_files())
        for content, name in ((b"GIF89a" + b"0" * 20, "x.gif"), (b"<script>alert(1)</script>", "evil.png"), (b"", "empty.png")):
            with self.subTest(name=name):
                res = self.create(image=(content, name))
                self.assertEqual(res.status_code, 400)
        self.assertEqual(len(self.uploaded_files()), before)

    def test_photo_must_be_under_5mb(self):
        res = self.create(image=(PNG + b"0" * (5 * 1024 * 1024), "big.png"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("5 MB", res.get_json()["error"])
        self.assertEqual(self.uploaded_files(), [])
        ok = self.create(image=(PNG + b"0" * (5 * 1024 * 1024 - len(PNG)), "limit.png"))
        self.assertEqual(ok.status_code, 201)

    def test_add_recipe_validation(self):
        bad = [
            {"name": ""},
            {"name": "x" * 81},
            {"ingredients": " , ,"},
            {"ingredients": ",".join(f"item{i}" for i in range(41))},
            {"ingredients": "a" * 61},
            {"instructions": "   "},
            {"instructions": "x" * 3001},
            {"time": "0"},
            {"time": "abc"},
            {"kcal": "-5"},
            {"kcal": "99999"},
            {"protein": "nan"},
            {"fat": "5000"},
            {"diet": ["Paleo"]},
            {"image": None},
        ]
        for fields in bad:
            with self.subTest(fields=fields):
                self.assertEqual(self.create(**fields).status_code, 400)
        self.assertEqual(self.uploaded_files(), [])          # nothing saved for rejected recipes
        self.assertEqual(len(self.recipes()), 15)

    def test_failed_save_removes_the_photo_and_rows(self):
        with sqlite3.connect(support.DB_PATH) as db:   # make the database refuse diet tags
            db.execute(
                "CREATE TRIGGER fail_diet BEFORE INSERT ON recipe_diets BEGIN SELECT RAISE(ABORT, 'boom'); END"
            )
        try:
            with self.assertRaises(sqlite3.Error):
                self.create(diet=["Vegan"])
        finally:
            with sqlite3.connect(support.DB_PATH) as db:
                db.execute("DROP TRIGGER fail_diet")
        self.assertEqual(self.uploaded_files(), [])          # photo removed again
        self.assertEqual(len(self.recipes()), 15)            # recipe row rolled back


if __name__ == "__main__":
    unittest.main()
