# VitaPlate backend (Flask + SQLite)

One server does everything: it serves the website and the API. No Node.js is needed any more.

## Run
- Windows:    double-click `run_windows.bat`
- Mac/Linux:  `./run_mac_linux.sh`
- Manual:     `pip install -r requirements.txt` then `python app.py`

## Open
http://127.0.0.1:5000/login.html   (do NOT open the html files by double-clicking)

## API
POST /api/register        {name, email, password}
POST /api/login           {email, password}
POST /api/logout
GET  /api/me
POST /api/reset-password  {email, password}

Pantry, recipes, favourites and ratings: see `../docs/PHASE1_PANTRY_API.md`
and `../docs/PHASE2_RECIPES_API.md`.

Everything is stored in `vitaplate.db` (created automatically, passwords are hashed).
The starter recipes are copied in from `seed_data.py` the first time the app starts.

## Tests
    python -m unittest discover -s tests -v

## Note
`frontend_patch/js/auth.js` is an OLD copy - do not copy it over `../vitaplate/js/auth.js`
(the file in `vitaplate/js/` is newer and includes the onboarding step).
