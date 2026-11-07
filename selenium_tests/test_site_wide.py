"""Navigation, dashboard, theme, responsive layout and console errors on all 8 pages."""
import time

import pytest
from selenium.webdriver.common.by import By

from helpers import (PAGES, all_, console_errors, has_horizontal_scroll, open_page, visible,
                     wait)

NAV = [("index.html", "Dashboard"), ("pantry.html", "Pantry"), ("recipes.html", "Recipes"),
       ("planner.html", "Meal planner"), ("shopping.html", "Shopping list"),
       ("health.html", "Health & BMI"), ("profile.html", "Profile"),
       ("settings.html", "Settings")]


def current_nav_href(driver):
    el = wait(driver).until(lambda d: d.find_elements(
        By.CSS_SELECTOR, ".sidebar nav a[aria-current='page']") or False)
    return el[0].get_attribute("href").rsplit("/", 1)[-1]


def click_nav(driver, href):
    link = driver.find_element(By.CSS_SELECTOR, f"nav.nav a[href='{href}']")
    if not link.is_displayed():                 # collapsed sidebar -> open hamburger first
        visible(driver, "#menuBtn").click()
        wait(driver).until(lambda d: link.is_displayed())
    link.click()


@pytest.mark.parametrize("page", PAGES)
def test_every_page_loads_with_shell(auth_driver, page):
    open_page(auth_driver, page)
    assert current_nav_href(auth_driver) == page
    assert len(all_(auth_driver, "nav.nav a")) == 8


@pytest.mark.parametrize("href,label", NAV[1:])
def test_sidebar_navigation(auth_driver, href, label):
    click_nav(auth_driver, href)
    wait(auth_driver).until(lambda d: href in d.current_url)
    assert current_nav_href(auth_driver) == href


def test_back_and_forward(auth_driver):
    for page in ("planner.html", "recipes.html", "pantry.html"):
        open_page(auth_driver, page)
        current_nav_href(auth_driver)
    auth_driver.back()
    assert current_nav_href(auth_driver) == "recipes.html"
    auth_driver.back()
    assert current_nav_href(auth_driver) == "planner.html"
    auth_driver.forward()
    assert current_nav_href(auth_driver) == "recipes.html"


@pytest.mark.parametrize("page", PAGES)
def test_refresh_keeps_session_and_page(auth_driver, page):
    open_page(auth_driver, page)
    current_nav_href(auth_driver)
    auth_driver.refresh()
    assert current_nav_href(auth_driver) == page
    assert "login.html" not in auth_driver.current_url


def test_dashboard_content(auth_driver):
    assert visible(auth_driver, "#hello").text
    wait(auth_driver).until(lambda d: len(all_(d, "#recommendations > *")) > 0)
    assert visible(auth_driver, "#mealPlanList") is not None


def test_dashboard_water_tracker(auth_driver):
    before = visible(auth_driver, "#waterCount").text
    visible(auth_driver, "#waterPlus").click()
    wait(auth_driver).until(lambda d: d.find_element(By.ID, "waterCount").text != before)
    after = auth_driver.find_element(By.ID, "waterCount").text
    visible(auth_driver, "#waterMinus").click()
    wait(auth_driver).until(lambda d: d.find_element(By.ID, "waterCount").text != after)


def test_theme_toggle_persists(auth_driver):
    html = auth_driver.find_element(By.TAG_NAME, "html")
    start = html.get_attribute("data-theme")
    visible(auth_driver, ".theme-toggle").click()
    flipped = html.get_attribute("data-theme")
    assert flipped != start
    auth_driver.refresh()
    visible(auth_driver, ".theme-toggle")
    assert auth_driver.find_element(By.TAG_NAME, "html").get_attribute("data-theme") == flipped


# ---------------------------------------------------------------- responsive
SIZES = {"desktop": (1440, 900), "tablet": (820, 1180), "mobile": (390, 844)}


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("size", SIZES)
def test_responsive_layout(auth_driver, set_viewport, size, page):
    width, height = SIZES[size]
    set_viewport(width, height)
    open_page(auth_driver, page)
    current_nav_href(auth_driver)
    assert not has_horizontal_scroll(auth_driver), f"horizontal scroll on {page} at {size}"
    if size == "desktop":
        assert visible(auth_driver, "#sidebar").is_displayed()
    else:
        assert visible(auth_driver, "#menuBtn").is_displayed()


# ------------------------------------------------------------- console errors
@pytest.mark.parametrize("page", [
    "index.html", "pantry.html", "recipes.html", "planner.html",
    pytest.param("shopping.html", marks=pytest.mark.xfail(
        reason="DEF-009: CSP blocks Unsplash/Flaticon images", strict=False)),
    "health.html", "profile.html", "settings.html"])
def test_no_console_errors(auth_driver, page):
    auth_driver.get_log("browser")
    open_page(auth_driver, page)
    current_nav_href(auth_driver)
    wait(auth_driver).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(1)                                   # let async fetches/images settle
    assert console_errors(auth_driver) == []
