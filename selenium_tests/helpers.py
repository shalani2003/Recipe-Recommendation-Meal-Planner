"""Shared helpers for the VitaPlate Selenium suite."""
import os

from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

# The Flask server serves the pages AND the API, so always test against port 5000
# (not VS Code Live Server on 5500, which has no /api).
BASE_URL = os.environ.get("VITAPLATE_URL", "http://127.0.0.1:5000").rstrip("/")
TIMEOUT = int(os.environ.get("VITAPLATE_TIMEOUT", "10"))

PAGES = [
    "index.html", "pantry.html", "recipes.html", "planner.html",
    "shopping.html", "health.html", "profile.html", "settings.html",
]

# Console noise that is not an app bug (offline fonts, favicon).
IGNORED_CONSOLE = (
    "fonts.googleapis.com", "fonts.gstatic.com", "favicon.ico",
    "ERR_INTERNET_DISCONNECTED", "ERR_NAME_NOT_RESOLVED",
)


def open_page(driver, page):
    driver.get(f"{BASE_URL}/{page}")


def wait(driver, timeout=None):
    return WebDriverWait(driver, timeout or TIMEOUT)


def visible(driver, css, timeout=None):
    return wait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, css)))


def clickable(driver, css, timeout=None):
    return wait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, css)))


def all_(driver, css):
    return driver.find_elements(By.CSS_SELECTOR, css)


def body_text(driver):
    return driver.find_element(By.TAG_NAME, "body").text


def wait_for_text(driver, css, expected, timeout=None):
    """Wait until any element matching `css` contains `expected` (case-insensitive)."""
    found = {}

    def check(d):
        for el in d.find_elements(By.CSS_SELECTOR, css):
            try:
                text = el.text
            except StaleElementReferenceException:
                continue
            if expected.lower() in text.lower():
                found["text"] = text
                return True
        return False

    wait(driver, timeout).until(check)
    return found["text"]


def wait_for_body_text(driver, expected, timeout=None):
    return wait_for_text(driver, "body", expected, timeout)


def type_into(driver, css, text):
    el = visible(driver, css)
    el.clear()
    if text != "":
        el.send_keys(text)
    return el


def select_option(driver, css, label):
    """Pick an <option> by value, falling back to its visible text (case-insensitive)."""
    select = Select(visible(driver, css))
    try:
        select.select_by_value(label)
        return
    except NoSuchElementException:
        pass
    for option in select.options:
        if option.text.strip().lower() == label.lower():
            select.select_by_visible_text(option.text)
            return
    raise AssertionError(f"No option {label!r} in {css}")


def js_click(driver, element):
    driver.execute_script("arguments[0].click()", element)


def accept_alert(driver, text=None, timeout=None):
    """Accept a native alert/confirm/prompt. For prompt() pass `text` to replace its value."""
    alert = wait(driver, timeout).until(EC.alert_is_present())
    message = alert.text
    if text is not None:
        alert.send_keys(text)
    alert.accept()
    return message


def dismiss_alert(driver, timeout=None):
    alert = wait(driver, timeout).until(EC.alert_is_present())
    message = alert.text
    alert.dismiss()
    return message


def maybe_accept_alert(driver, timeout=1.5):
    try:
        accept_alert(driver, timeout=timeout)
        return True
    except Exception:
        return False


def has_horizontal_scroll(driver):
    return driver.execute_script(
        "return document.documentElement.scrollWidth - window.innerWidth") > 1


def console_errors(driver):
    errors = []
    for entry in driver.get_log("browser"):
        if entry.get("level") != "SEVERE":
            continue
        message = entry.get("message", "")
        if any(token in message for token in IGNORED_CONSOLE):
            continue
        errors.append(message)
    return errors


def chip_selected(element):
    """Toggle chips are shown as pressed; accept aria-pressed or a CSS state class."""
    if element.get_attribute("aria-pressed") == "true":
        return True
    classes = (element.get_attribute("class") or "").split()
    return any(c in classes for c in ("on", "active", "selected", "is-on", "is-active"))
