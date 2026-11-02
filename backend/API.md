# VitaPlate API reference (tasks P1 to P7)

All paths start with `/api`. Data is JSON. Errors use `{"error": "message"}`.
Every endpoint except register, login, forgot-password and reset-password needs a logged-in session cookie (401 otherwise).
Writes from another website are refused (403).

## Account and login

| Method | Path | Body | Result |
|---|---|---|---|
| POST | `/register` | `name`, `email`, `password` (8+ chars, 1 number) | 201 `{user, recovery_code}`. The code is shown **once**. 409 if the email exists |
| POST | `/login` | `email`, `password` | `{user}`. Same message for a wrong password and an unknown email. 429 after 8 tries in 5 minutes |
| POST | `/logout` | none | `{ok}` |
| GET | `/me` | none | `{user}` |
| POST | `/forgot-password` | `email`, `recovery_code` | `{reset_token, expires_in}` (15 minutes). Same 400 message whether the email exists or not |
| POST | `/reset-password` | `token`, `password` | `{ok, recovery_code}`. The token works once; a new recovery code replaces the old one |

## Pantry

`GET /pantry?today=YYYY-MM-DD` (the browser sends its local date) returns
`{items: [{id, name, category, quantity, unit, expiry_date, cat, qty, exp, days_left, state}], summary: {items, use_soon, expired}}`.
`state` is `expired`, `today`, `soon` (1 to 3 days), `ok` or `none`. Expired items are not counted in `use_soon`.

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/pantry` | `name`, `quantity` (or legacy `qty`, default 1, decimals allowed, > 0), `unit`, `category` (or legacy `cat`), `expiry_date` (or legacy `exp`) | 201 new, 200 merged. Same name + same unit adds the amounts and keeps the earlier expiry. A different unit stays separate |
| GET | `/pantry/<id>` | none | `{item}`; 404 if the item is not owned by the logged-in user |
| PUT | `/pantry/<id>` | any of `name`, `quantity`/`qty`, `unit`, `category`/`cat`, `expiry_date`/`exp` | 409 if it would duplicate another item |
| PATCH | `/pantry/<id>/quantity` | `delta` (for example 1 or -1) | At 0 or below the item is removed: `{deleted: true}` |
| DELETE | `/pantry/<id>` | none | |
| DELETE | `/pantry` | none | `{removed: n}` |

Units: `pcs g kg ml l cups`. Categories: `Vegetables Fruits Grains Protein Dairy Spices & sauces Other`.
`expiry_date` (or `exp`) is a date `YYYY-MM-DD` or empty. Pantry responses include the canonical names (`quantity`, `category`, `expiry_date`) and legacy aliases (`qty`, `cat`, `exp`) for existing clients.

## Diets, allergies, onboarding

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/dietary` | none | `{diets, allergies, onboarding_completed}` |
| PUT | `/dietary` | any of `diets`, `allergies`, `onboarding_completed` | Same shape. Missing keys stay unchanged. Diets: `Vegetarian Vegan Gluten-free Dairy-free Nut-free Halal Low sugar`. Allergies are lower-cased, no duplicates, up to 20 |

## Settings

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/settings` | none | `{name, email, preferences, picture_url, has_recovery_code}` |
| PUT | `/settings` | any of `name`, `email`, `preferences` | Same shape. 409 if the email belongs to another account. Preferences: `notificationMode` (`all`/`important`/`off`), `mealReminders`, `weeklySummary` |
| POST | `/settings/password` | `current_password`, `new_password` | `{ok}`; 403 if the current password is wrong |
| POST | `/settings/recovery-code` | `password` | `{recovery_code}`: a new code (for accounts created before codes existed) |
| POST | `/settings/picture` | form field `picture` (JPG, PNG, WebP, up to 2 MB) | 201 `{picture_url}`. The real file bytes are checked, not the name |
| GET | `/settings/picture` | none | The picture file (404 if none) |
| DELETE | `/settings/picture` | none | `{ok}` |
| DELETE | `/account/data` | `{"confirm": true}` | Deletes only this user's saved data and picture. The account and login stay: `{account_kept: true, logged_in: true, message}` |

## Profile

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/profile` | none | `{name, age, height, weight, allergies, health_notes, calorie_goal, target_weight}` |
| PUT | `/profile` | Any profile fields; `allergies` can be a comma-separated string or list | Same shape. Height: 100-230 cm; weight and target weight: 25-250 kg; calorie goal: 1000-4000 kcal; age: 1-120 |

Profile and dietary allergies are kept in sync. Updating profile name also updates the account name used by settings and `/me`.

## Recipes (temporary, until routes/recipes.py)

| Method | Path | Notes |
|---|---|---|
| GET | `/recipes` | Public. `[{id, name, ingredients, instructions, image}]` |
| POST | `/recipes` | multipart: `name`, `ingredients` (comma separated), `instructions`, `imageFile` (optional; JPG/PNG/WebP, up to 5 MB). Reply: `{success, message, recipe}` |
