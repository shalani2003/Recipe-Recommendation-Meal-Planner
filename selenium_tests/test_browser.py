from selenium import webdriver


def test_vitaplate_login_page():
    driver = webdriver.Chrome()

    try:
        driver.get("http://127.0.0.1:5000/login.html")

        assert "VitaPlate" in driver.title

    finally:
        driver.quit()