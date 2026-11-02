"""
Starter recipes. They are copied into the database the first time the app starts
(only when the recipes table is empty), so edit this list BEFORE the first run
or change recipes in the database afterwards.

- ids 1-8  : the recipes that used to live in vitaplate/js/data.js. The ids are kept
             because saved meal plans, favourites and ratings refer to them.
- ids 9-15 : the recipes that used to live in the Node server (server.js).
- kcal / protein / carbs / fat are None where the old data had no nutrition values.
- diet tags of ids 9-15 were worked out from their ingredient lists - please review them.
"""
import sqlite3

from database import DB_PATH

V, VG, GF, DF, H = "Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Halal"

# (id, name, time, kcal, protein, carbs, fat, diets, ingredients, instructions, image)
SEED_RECIPES = [
    (1, "Chicken & broccoli bowl", 25, 480, 38, 40, 16, [H, DF, GF], ["Chicken", "Broccoli", "Rice"],
     "Cook the rice. Pan-fry the chicken until golden and steam the broccoli, then serve everything together in a bowl.",
     "assets/food/chickenandbrocoli.jpg"),
    (2, "Pumpkin dhal curry", 30, 390, 16, 58, 10, [V, VG, GF, DF, H], ["Pumpkin", "Dhal", "Coconut", "Rice"],
     "Simmer the dhal with the pumpkin until soft, stir in coconut milk and season, then serve with rice.",
     "assets/food/pumpkin.jpg"),
    (3, "Egg fried rice", 15, 520, 18, 70, 18, [V, DF, H], ["Eggs", "Rice", "Onion"],
     "Fry the onion, add the cooked rice, push it aside and scramble the eggs, then mix everything together and season.",
     "assets/food/Eggrice.jpg"),
    (4, "Tomato omelette", 10, 310, 20, 8, 22, [V, GF, H, DF], ["Eggs", "Tomato", "Onion"],
     "Beat the eggs, soften the onion and tomato in a pan, pour in the eggs and cook until set.",
     "assets/food/eggandtomato.jpg"),
    (5, "Avocado toast", 10, 340, 9, 32, 20, [V, VG, DF, H], ["Avocado", "Bread", "Tomato"],
     "Toast the bread, mash the avocado on top and finish with sliced tomato and a pinch of salt.",
     "assets/food/avocado.jpg"),
    (6, "Coconut roti & sambol", 20, 420, 9, 60, 15, [V, VG, DF, H], ["Coconut", "Flour", "Onion"],
     "Mix the flour with scraped coconut and a little onion into a dough, shape into rotis and cook on a hot pan until golden.",
     "assets/food/polroti.jpg"),
    (7, "Carrot & lentil soup", 35, 280, 15, 40, 5, [V, VG, GF, DF, H], ["Carrot", "Dhal", "Onion"],
     "Simmer the dhal with the carrot and onion until soft, blend if you like it smooth, and season.",
     "assets/food/carrot.jpg"),
    (8, "Creamy chicken curry", 40, 560, 42, 22, 32, [GF, H], ["Chicken", "Coconut", "Onion", "Curry powder"],
     "Brown the onion, add the curry powder and chicken, pour in coconut milk and simmer until the chicken is cooked.",
     "assets/food/creamchicken.jpg"),
    (9, "Chickpea Salad Bowl", None, None, None, None, None, [V, VG, GF, DF, H],
     ["chickpeas", "cucumber", "tomato", "lemon"],
     "Mix the ingredients in a bowl and season with lemon.", "assets/food/api-chickpea-salad.jpg"),
    (10, "Spinach Omelette", None, None, None, None, None, [V, GF, DF, H],
     ["eggs", "spinach", "onion"],
     "Cook the onion and spinach, add beaten eggs, and cook until set.", "assets/food/api-spinach-omelette.jpg"),
    (11, "Mango Yogurt Bowl", None, None, None, None, None, [V, GF, H],
     ["mango", "yogurt", "honey"],
     "Mix the mango and yogurt, then drizzle with honey.", "assets/food/api-mango-yogurt.jpg"),
    (12, "Chicken Quinoa Bowl", None, None, None, None, None, [GF, DF, H],
     ["chicken", "quinoa", "spinach", "lemon"],
     "Cook the quinoa and chicken, then serve with spinach and lemon.", "assets/food/chicken-quinoa.jpg"),
    (13, "Baked Salmon with Vegetables", None, None, None, None, None, [GF, DF, H],
     ["salmon", "broccoli", "lemon", "olive oil"],
     "Bake the salmon and broccoli with olive oil and lemon until cooked.", "assets/food/baked-salmon.jpg"),
    (14, "Lentil Vegetable Soup", None, None, None, None, None, [V, VG, GF, DF, H],
     ["lentils", "carrot", "onion", "vegetable broth"],
     "Simmer the lentils and vegetables in broth until tender.", "assets/food/lentil-soup.jpg"),
    (15, "Vegetable Rice Bowl", None, None, None, None, None, [V, VG, GF, DF, H],
     ["rice", "carrot", "peas"],
     "Cook the rice and vegetables, then serve together.", "assets/food/vegetable-rice.jpeg"),
]


def seed_recipes():
    """Insert the starter recipes if the recipes table is empty."""
    with sqlite3.connect(DB_PATH) as db:
        if db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]:
            return
        for rid, name, minutes, kcal, protein, carbs, fat, diets, ingredients, instructions, image in SEED_RECIPES:
            db.execute(
                """INSERT INTO recipes (id, name, instructions, image, time_minutes, kcal, protein, carbs, fat)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (rid, name, instructions, image, minutes, kcal, protein, carbs, fat),
            )
            db.executemany(
                "INSERT INTO recipe_ingredients (recipe_id, position, name) VALUES (?, ?, ?)",
                [(rid, position, ingredient) for position, ingredient in enumerate(ingredients)],
            )
            db.executemany(
                "INSERT INTO recipe_diets (recipe_id, diet) VALUES (?, ?)", [(rid, diet) for diet in diets]
            )
