"""Health/BMI + weight journey + water, Profile, Settings (FE-046..051, FE-057)."""
import pytest
from selenium.webdriver.common.by import By

from helpers import (BASE_URL, accept_alert, body_text, dismiss_alert, open_page, type_into,
                     visible, wait, wait_for_text)


# ------------------------------------------------------------------- health
def calculate(driver, height, weight, target=None):
    open_page(driver, "health.html")
    type_into(driver, "#h", height)
    type_into(driver, "#w", weight)
    if target is not None:
        type_into(driver, "#t", target)
    visible(driver, "#go").click()


@pytest.mark.parametrize("h,w,bmi,label", [
    ("170", "70", "24.2", "Healthy"), ("160", "45", "17.6", "Underweight"),
    ("170", "85", "29.4", "Overweight"), ("170", "95", "32.9", "Obese")])
def test_bmi_valid_values(auth_driver, h, w, bmi, label):
    calculate(auth_driver, h, w)
    wait_for_text(auth_driver, "#out", bmi)
    assert label.lower() in visible(auth_driver, "#out").text.lower()


@pytest.mark.parametrize("h,w,error_css,message", [
    ("0", "70", "#heightError", "between 100 and 230"),
    ("-170", "70", "#heightError", "between 100 and 230"),
    ("99", "70", "#heightError", "between 100 and 230"),
    ("170", "-5", "#weightError", "between 25 and 250"),
    ("170", "0", "#weightError", "between 25 and 250"),
    ("170", "251", "#weightError", "between 25 and 250"),
    ("", "70", "#heightError", "required"),
    ("170", "", "#weightError", "required")])
def test_bmi_rejects_invalid_values(auth_driver, h, w, error_css, message):
    calculate(auth_driver, h, w)
    wait_for_text(auth_driver, error_css, message)
    assert auth_driver.find_element(By.ID, "out").text.strip() == ""


def test_target_weight_message_and_validation(auth_driver):
    calculate(auth_driver, "170", "70", "65")
    wait_for_text(auth_driver, "body", "5.0 kg to lose")
    type_into(auth_driver, "#t", "10")
    visible(auth_driver, "#go").click()
    wait_for_text(auth_driver, "#targetError", "between 25 and 250")


def test_water_tracker_on_health_page(auth_driver):
    open_page(auth_driver, "health.html")
    visible(auth_driver, "#waterUp").click()
    wait_for_text(auth_driver, "#waterCount", "1 glass")
    visible(auth_driver, "#waterDown").click()
    wait_for_text(auth_driver, "#waterCount", "0 glasses")


def test_log_current_weight(auth_driver):
    open_page(auth_driver, "health.html")
    type_into(auth_driver, "#w", "70")
    visible(auth_driver, "#logWeight").click()
    wait_for_text(auth_driver, "#weightHistory", "70 kg")


# ------------------------------------------------------------------ profile
def test_profile_saves_and_reloads(auth_driver):
    open_page(auth_driver, "profile.html")
    type_into(auth_driver, "#n", "QA Tester")
    type_into(auth_driver, "#age", "30")
    type_into(auth_driver, "#profileHeight", "170")
    type_into(auth_driver, "#profileWeight", "70")
    type_into(auth_driver, "#allergies", "peanut, shellfish")
    type_into(auth_driver, "#infections", "none")
    visible(auth_driver, "#sv").click()
    wait(auth_driver).until(lambda d: d.find_element(By.ID, "ok").text.strip() != "")
    auth_driver.refresh()
    wait(auth_driver).until(lambda d: d.find_element(By.ID, "age").get_attribute("value") == "30")
    assert auth_driver.find_element(By.ID, "profileHeight").get_attribute("value") == "170"
    assert auth_driver.find_element(By.ID, "profileWeight").get_attribute("value") == "70"
    assert "peanut" in auth_driver.find_element(By.ID, "allergies").get_attribute("value")


@pytest.mark.parametrize("field,value,error_css", [
    ("#n", "a", "#nameError"), ("#age", "0", "#ageError"),
    ("#profileHeight", "50", "#heightError"), ("#profileWeight", "10", "#weightError")])
def test_profile_validation(auth_driver, field, value, error_css):
    open_page(auth_driver, "profile.html")
    type_into(auth_driver, field, value)
    visible(auth_driver, "#sv").click()
    wait(auth_driver).until(lambda d: d.find_element(By.CSS_SELECTOR, error_css).text.strip() != "")


def test_reset_all_data_cancel_then_confirm(auth_driver, api):
    api.post(f"{BASE_URL}/api/pantry", json={"name": "Reset me", "quantity": 1, "unit": "pcs"},
             timeout=10)
    open_page(auth_driver, "profile.html")
    visible(auth_driver, "#rs").click()
    assert "Delete all VitaPlate data" in dismiss_alert(auth_driver)
    assert "reset me" in api.get(f"{BASE_URL}/api/pantry", timeout=10).text.lower()
    visible(auth_driver, "#rs").click()
    accept_alert(auth_driver)
    wait(auth_driver).until(lambda d: "reset me" not in api.get(
        f"{BASE_URL}/api/pantry", timeout=10).text.lower())
    assert api.get(f"{BASE_URL}/api/me", timeout=10).status_code == 200   # login is kept


# ----------------------------------------------------------------- settings
def test_settings_name_change_persists(auth_driver, account, api):
    open_page(auth_driver, "settings.html")
    type_into(auth_driver, "#name", "QA Renamed")
    try:
        visible(auth_driver, "#save").click()
        wait(auth_driver).until(lambda d: d.find_element(By.ID, "saved").text.strip() != "")
        auth_driver.refresh()
        wait(auth_driver).until(
            lambda d: d.find_element(By.ID, "name").get_attribute("value") == "QA Renamed")
        assert visible(auth_driver, ".user-card b").text == "QA Renamed"
    finally:
        api.put(f"{BASE_URL}/api/settings", json={"name": account.name}, timeout=10)


def test_change_password_with_wrong_current_password(auth_driver):
    open_page(auth_driver, "settings.html")
    type_into(auth_driver, "#currentPassword", "definitely-wrong1")
    type_into(auth_driver, "#newPassword", "BrandNewPass123")
    visible(auth_driver, "#save").click()
    wait(auth_driver).until(lambda d: d.find_element(By.ID, "error").text.strip() != "")
