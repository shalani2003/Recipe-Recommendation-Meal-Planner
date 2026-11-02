# VitaPlate backend

One server (Flask + SQLite) serves the web pages **and** the whole API on port 5000.
The old Node server (`server.js`) is retired.

## Run

Windows: double-click `run_windows.bat`. Mac/Linux: `./run_mac_linux.sh`.
Then open <http://127.0.0.1:5000/login.html>.

Developing? `set VITAPLATE_DEBUG=1` (Windows) or `export VITAPLATE_DEBUG=1` before running to get auto-reload.
Debug mode is off by default, so it is off for the demo.

## Test

```
pip install -r requirements-dev.txt
python -m pytest -q
```

The same tests run on GitHub for every push (`.github/workflows/backend-ci.yml`).

## Folder map (one owner per file)

| File | What it does | Owner |
|---|---|---|
| `app.py` | Creates the app, loads every module | Jayasundara |
| `db.py` | All tables, start-up creation, sample data for a new account | Jayasundara |
| `auth_helpers.py` | `login_required`, `error()`, validation, rate limit, security headers | Jayasundara |
| `routes/auth.py` | register, login, logout, me, forgot/reset password | Jayasundara |
| `routes/pantry.py`, `services/pantry_service.py` | Pantry API and the merge rule | Jayasundara |
| `routes/dietary.py` | Diets, allergies, onboarding flag | Jayasundara |
| `routes/settings.py` | Settings, change password, picture, reset all data | Jayasundara |
| `routes/recipes_legacy.py` | Temporary recipes API (ported from Node). Delete when `routes/recipes.py` exists | Jayathilaka |
| `routes/recipes.py`, `recommend.py`, `shopping.py` | To be added | Jayathilaka |
| `routes/plan.py`, `nutrition.py`, `health.py`, `profile.py`, `dashboard.py` | To be added | Dilshan |

## How a teammate adds a module

1. Create `routes/<name>.py` with `bp = Blueprint("<name>", __name__, url_prefix="/api")`.
2. Protect every route with `@login_required` and read the user from `g.user_id`.
3. Always filter by `user_id` in SQL. Return errors with `error("message", status)`.
4. Your tables already exist in `db.py` (change them there and tell the owner).
5. Do not edit `app.py`: modules named `routes.recipes`, `recommend`, `shopping`, `plan`, `nutrition`, `health`, `profile`, `dashboard` load automatically.
6. Add tests in `tests/` (see `tests/conftest.py`: `user` and `user2` fixtures are two logged-in accounts).

Pantry helper for the shopping list ("move to pantry"):
`from services.pantry_service import add_item, parse_category` then `add_item(db, g.user_id, name, cat, qty, unit, exp)`.

See `API.md` for every endpoint.
