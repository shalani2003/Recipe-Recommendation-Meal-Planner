# VitaPlate Selenium suite
1. `pip install -r requirements-selenium.txt`
2. Start the app: `cd backend && python app.py`  (http://127.0.0.1:5000)
3. From this folder: `pytest`  -> report in `reports/VitaPlate_Test_Report.html`
Options: `HEADED=1` (watch the browser), `VITAPLATE_URL=...`, `ALLOW_RECIPE_CREATE=1` (also runs the add-recipe test).
