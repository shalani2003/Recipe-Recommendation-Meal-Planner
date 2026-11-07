"""Fixtures for the VitaPlate Selenium suite.

Run the backend first:   cd backend && python app.py      (http://127.0.0.1:5000)
Then:                    pytest

Env vars: VITAPLATE_URL (default http://127.0.0.1:5000), HEADED=1 to watch the browser.
"""
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from helpers import BASE_URL, visible

PASSWORD = "VitaPlate2026x"   # 8+ chars and at least one digit (backend rule)
REPORT_DIR = Path("reports")


# ---------------------------------------------------------------- environment
@pytest.fixture(scope="session", autouse=True)
def backend_up():
    """Fail fast, with a clear message, if the Flask server is not the one being tested."""
    try:
        response = requests.get(f"{BASE_URL}/api/me", timeout=5)
    except requests.RequestException as exc:
        pytest.exit(f"Cannot reach {BASE_URL}. Start the backend (python app.py). {exc}",
                    returncode=2)
    if response.status_code not in (200, 401):
        pytest.exit(f"{BASE_URL}/api/me returned {response.status_code}. This looks like a "
                    "static server (e.g. Live Server). Use the Flask server on port 5000.",
                    returncode=2)


@pytest.fixture(scope="session")
def browser():
    options = Options()
    if os.environ.get("HEADED") != "1":
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,900")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    drv = webdriver.Chrome(options=options)   # Selenium Manager fetches chromedriver
    yield drv
    drv.quit()


@pytest.fixture
def driver(browser):
    """A logged-OUT browser: cookies and storage cleared before every test."""
    try:
        browser.switch_to.alert.dismiss()
    except Exception:
        pass
    browser.get(f"{BASE_URL}/api/me")          # plain JSON page on the right origin
    browser.delete_all_cookies()
    browser.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    browser.set_window_size(1440, 900)
    browser.get_log("browser")                 # drain old console entries
    yield browser


@pytest.fixture
def set_viewport(driver):
    """Emulate a viewport (works for phone widths below Chrome's minimum window size)."""
    def _set(width, height):
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 600})
    yield _set
    driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})


# ------------------------------------------------------------------- accounts
@dataclass
class Account:
    name: str
    email: str
    password: str
    session: requests.Session


def _register(onboarded):
    session = requests.Session()
    email = f"qa_{uuid.uuid4().hex[:10]}@example.com"
    name = "QA Tester"
    response = session.post(f"{BASE_URL}/api/register", timeout=20,
                            json={"name": name, "email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    if onboarded:
        session.put(f"{BASE_URL}/api/dietary", json={"onboarding_completed": True}, timeout=10)
    return Account(name, email, PASSWORD, session)


@pytest.fixture(scope="session")
def account():
    """One registered, onboarded user shared by the whole run (created through the API)."""
    return _register(onboarded=True)


@pytest.fixture
def new_account():
    """A fresh user who has NOT finished onboarding."""
    return _register(onboarded=False)


@pytest.fixture
def api(account):
    return account.session


def reset_user_data(session):
    for path in ("/api/pantry", "/api/shopping", "/api/meal-plan"):
        session.delete(f"{BASE_URL}{path}", timeout=10)
    session.put(f"{BASE_URL}/api/dietary", json={"diets": [], "allergies": []}, timeout=10)
    session.put(f"{BASE_URL}/api/water", json={"glasses": 0}, timeout=10)


@pytest.fixture
def auth_driver(driver, account):
    """A browser that is already logged in (session cookie injected) with clean test data."""
    reset_user_data(account.session)
    driver.get(f"{BASE_URL}/api/me")
    for cookie in account.session.cookies:
        driver.add_cookie({"name": cookie.name, "value": cookie.value, "path": "/"})
    driver.get(f"{BASE_URL}/index.html")
    visible(driver, "#hello")
    return driver


# -------------------------------------------- screenshot into the HTML report
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    drv = item.funcargs.get("driver") or item.funcargs.get("auth_driver")
    if drv is None:
        return
    try:
        REPORT_DIR.joinpath("screenshots").mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w.-]", "_", item.name)
        drv.save_screenshot(str(REPORT_DIR / "screenshots" / f"{safe}.png"))
        from pytest_html import extras
        report.extras = getattr(report, "extras", []) + [
            extras.png(drv.get_screenshot_as_base64())]
    except Exception:
        pass
