"""Login, registration, logout and route protection (login page = the 3 failing tests)."""
import uuid

import pytest
from selenium.webdriver.common.by import By

from helpers import (BASE_URL, accept_alert, js_click, open_page, type_into, visible, wait,
                     wait_for_text)


def open_login(driver):
    open_page(driver, "login.html")
    visible(driver, "#loginForm")


def submit_login(driver, email, password):
    type_into(driver, "#email", email)
    type_into(driver, "#pw", password)          # NOTE: the id is "pw", not "password"
    visible(driver, "#loginForm button[type=submit]").click()


def test_login_page_opens(driver):
    open_login(driver)
    assert "Log in" in driver.title
    assert visible(driver, "h2").text == "Log in"


def test_email_and_password_fields_exist(driver):
    open_login(driver)
    assert driver.find_element(By.ID, "email").is_displayed()
    assert driver.find_element(By.ID, "pw").is_displayed()


def test_show_hide_password_toggle(driver):
    open_login(driver)
    field = visible(driver, "#pw")
    assert field.get_attribute("type") == "password"
    visible(driver, "button[data-pw='pw']").click()
    assert field.get_attribute("type") == "text"
    visible(driver, "button[data-pw='pw']").click()
    assert field.get_attribute("type") == "password"


def test_empty_login_shows_validation(driver):
    open_login(driver)
    visible(driver, "#loginForm button[type=submit]").click()
    assert wait_for_text(driver, "#emailErr", "Enter a valid email")
    assert wait_for_text(driver, "#pwErr", "Enter your password")


def test_malformed_email_rejected(driver):
    open_login(driver)
    submit_login(driver, "not-an-email", "Whatever123")
    assert wait_for_text(driver, "#emailErr", "Enter a valid email")


def test_invalid_login_shows_error(driver):
    open_login(driver)
    submit_login(driver, f"nobody_{uuid.uuid4().hex[:8]}@example.com", "WrongPassword123")
    wait_for_text(driver, "#alert.show", "Email or password is incorrect")
    assert "login.html" in driver.current_url


def test_valid_login_goes_to_dashboard(driver, account):
    open_login(driver)
    submit_login(driver, account.email, account.password)
    wait(driver).until(lambda d: "index.html" in d.current_url)
    assert visible(driver, "#hello")


def test_login_before_onboarding_goes_to_onboarding(driver, new_account):
    open_login(driver)
    submit_login(driver, new_account.email, new_account.password)
    wait(driver).until(lambda d: "onboarding.html" in d.current_url)


def test_forgot_password_and_register_links(driver):
    open_login(driver)
    visible(driver, "a[href='reset-password.html']").click()
    wait(driver).until(lambda d: "reset-password.html" in d.current_url)
    open_login(driver)
    visible(driver, "a[href='register.html']").click()
    wait(driver).until(lambda d: "register.html" in d.current_url)


def test_register_validation_messages(driver):
    open_page(driver, "register.html")
    visible(driver, "#regForm button[type=submit]").click()
    assert wait_for_text(driver, "#nameErr", "Enter your name")
    assert wait_for_text(driver, "#emailErr", "Enter a valid email")
    assert wait_for_text(driver, "#pwErr", "8+ characters")
    wait_for_text(driver, "#alert.show", "accept the terms")


def test_register_password_mismatch(driver):
    open_page(driver, "register.html")
    type_into(driver, "#name", "Mismatch Tester")
    type_into(driver, "#email", f"qa_{uuid.uuid4().hex[:8]}@example.com")
    type_into(driver, "#pw", "Passw0rdUI1")
    type_into(driver, "#pw2", "Different123")
    js_click(driver, driver.find_element(By.ID, "terms"))
    visible(driver, "#regForm button[type=submit]").click()
    assert wait_for_text(driver, "#pw2Err", "do not match")


def test_register_new_account_via_ui(driver):
    """Creates one real account (recovery code arrives in a native prompt())."""
    open_page(driver, "register.html")
    type_into(driver, "#name", "UI Tester")
    type_into(driver, "#email", f"qa_ui_{uuid.uuid4().hex[:8]}@example.com")
    type_into(driver, "#pw", "Passw0rdUI1")
    type_into(driver, "#pw2", "Passw0rdUI1")
    js_click(driver, driver.find_element(By.ID, "terms"))
    visible(driver, "#regForm button[type=submit]").click()
    assert "recovery code" in accept_alert(driver).lower()
    wait(driver).until(lambda d: "registered=1" in d.current_url)
    wait_for_text(driver, "#alert.show", "Account created")


def test_logout_returns_to_login(auth_driver):
    visible(auth_driver, "#logout").click()
    wait(auth_driver).until(lambda d: "login.html" in d.current_url)


@pytest.mark.parametrize("page", ["pantry.html", "planner.html", "profile.html"])
def test_protected_pages_redirect_when_logged_out(driver, page):
    open_page(driver, page)
    wait(driver).until(lambda d: "login.html" in d.current_url)
