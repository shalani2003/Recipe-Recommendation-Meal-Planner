import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "http://127.0.0.1:5000"


@pytest.fixture
def driver():
    browser = webdriver.Chrome()
    browser.maximize_window()
    yield browser
    browser.quit()


def test_login_page_opens(driver):
    driver.get(BASE_URL + "/login.html")
    assert driver.title != ""


def test_email_field_exists(driver):
    driver.get(BASE_URL + "/login.html")
    assert driver.find_element(By.ID, "email").is_displayed()


def test_password_field_exists(driver):
    driver.get(BASE_URL + "/login.html")
    assert driver.find_element(By.ID, "password").is_displayed()


def test_invalid_login(driver):
    driver.get(BASE_URL + "/login.html")

    driver.find_element(By.ID, "email").send_keys(
        "invalid_user@example.com"
    )

    driver.find_element(By.ID, "password").send_keys(
        "WrongPassword123"
    )

    driver.find_element(
        By.CSS_SELECTOR, "button[type='submit']"
    ).click()

    WebDriverWait(driver, 10).until(
        lambda d: (
            d.find_elements(
                By.CSS_SELECTOR,
                ".error, .alert, [role='alert']"
            )
            or d.find_elements(
                By.CSS_SELECTOR,
                "input:invalid"
            )
        )
    )