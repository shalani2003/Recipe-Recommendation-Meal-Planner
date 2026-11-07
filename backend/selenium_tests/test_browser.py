from selenium import webdriver
from selenium.webdriver.common.by import By


def test_vitaplate_login_page():
    driver = webdriver.Chrome()

    try:
        driver.get("http://127.0.0.1:5000/login.html")

        assert "VitaPlate" in driver.title

    finally:
        driver.quit()