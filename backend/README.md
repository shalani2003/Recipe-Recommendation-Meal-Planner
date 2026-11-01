# VitaPlate backend (Flask + SQLite)

## 1. Install the frontend patch (one time)
Copy `frontend_patch/js/auth.js` over `../vitaplate/js/auth.js` (replace the old file).

## 2. Run
- Windows:    double-click `run_windows.bat`
- Mac/Linux:  `./run_mac_linux.sh`
- Manual:     `pip install -r requirements.txt` then `python app.py`

## 3. Open
http://127.0.0.1:5000/login.html   (do NOT open the html files by double-clicking)

## API
POST /api/register        {name, email, password}
POST /api/login           {email, password}
POST /api/logout
GET  /api/me
POST /api/reset-password  {email, password}

Users are stored in `vitaplate.db` (created automatically). Passwords are hashed.
