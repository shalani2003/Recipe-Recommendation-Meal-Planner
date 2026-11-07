from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_invalid_login():
    driver = webdriver.Chrome()

    try:
        driver.get("http://127.0.0.1:5000/login.html")

        email = driver.find_element(By.ID, "email")
        password = driver.find_element(By.ID, "password")

        email.send_keys("invalid_user@example.com")
        password.send_keys("WrongPassword123")

        driver.find_element(
            By.CSS_SELECTOR, "button[type='submit']"
        ).click()

        # Wait for an error message or validation feedback
        WebDriverWait(driver, 10).until(
            lambda d: d.find_elements(
                By.CSS_SELECTOR, ".error, .alert, [role='alert']"
            )
        )

    finally:
        driver.quit()