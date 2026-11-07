"""Recipes page (FE-024 .. FE-035)."""
import os
import uuid

import pytest
from selenium.webdriver.common.by import By

from helpers import (all_, body_text, chip_selected, open_page, type_into, visible, wait,
                     wait_for_text)


def open_recipes(driver):
    open_page(driver, "recipes.html")
    wait(driver).until(lambda d: len(all_(d, ".rcard")) > 0)


def test_recipe_cards_are_listed(auth_driver):
    open_recipes(auth_driver)
    first = all_(auth_driver, ".rcard")[0]
    assert first.find_element(By.CSS_SELECTOR, ".recipe-photo")
    assert "kcal" in first.text and "min" in first.text


def test_search_finds_known_recipe(auth_driver):
    open_recipes(auth_driver)
    type_into(auth_driver, "#q", "omelette")
    wait(auth_driver).until(lambda d: any(
        "omelette" in c.text.lower() for c in all_(d, ".rcard") if c.is_displayed()))


def test_search_partial_text(auth_driver):
    open_recipes(auth_driver)
    type_into(auth_driver, "#q", "om")
    wait(auth_driver).until(lambda d: any(
        "om" in c.text.lower() for c in all_(d, ".rcard") if c.is_displayed()))


def test_search_without_match_shows_empty_state(auth_driver):
    open_recipes(auth_driver)
    type_into(auth_driver, "#q", "zzzqqq")
    wait_for_text(auth_driver, "body", "Nothing matches these filters")
    wait_for_text(auth_driver, "#api-recipe-count", "0 recipes")


def test_filter_tabs_toggle(auth_driver):
    open_recipes(auth_driver)
    for mode in ("now", "fav", "all"):
        tab = visible(auth_driver, f".tab[data-m='{mode}']")
        tab.click()
        wait(auth_driver).until(lambda d: d.find_element(
            By.CSS_SELECTOR, f".tab[data-m='{mode}']").get_attribute("aria-pressed") == "true")


def test_favourite_add_persist_remove(auth_driver):
    open_recipes(auth_driver)
    heart = all_(auth_driver, ".rcard .heart")[0]
    assert heart.get_attribute("aria-pressed") == "false"
    heart.click()
    try:
        wait(auth_driver).until(lambda d: all_(d, ".rcard .heart")[0]
                                .get_attribute("aria-pressed") == "true")
        auth_driver.refresh()
        wait(auth_driver).until(lambda d: len(all_(d, ".rcard")) > 0)
        visible(auth_driver, ".tab[data-m='fav']").click()
        wait(auth_driver).until(lambda d: len([c for c in all_(d, ".rcard")
                                               if c.is_displayed()]) >= 1)
    finally:
        visible(auth_driver, ".tab[data-m='all']").click()
        wait(auth_driver).until(lambda d: len(all_(d, ".rcard")) > 0)
        heart = all_(auth_driver, ".rcard .heart")[0]
        if heart.get_attribute("aria-pressed") == "true":
            heart.click()
            wait(auth_driver).until(lambda d: all_(d, ".rcard .heart")[0]
                                    .get_attribute("aria-pressed") == "false")


def stars_on(driver):
    return len(all_(driver, ".rcard:first-of-type [data-r].on")) or len(
        driver.find_elements(By.XPATH, "(//article[contains(@class,'rcard')])[1]//button[@data-r and contains(@class,'on')]"))


def test_rating_set_and_clear(auth_driver):
    open_recipes(auth_driver)
    star = lambda d: d.find_elements(By.XPATH,
        "(//article[contains(@class,'rcard')])[1]//button[contains(@data-r, ':4')]")[0]
    star(auth_driver).click()
    wait(auth_driver).until(lambda d: stars_on(d) == 4)
    star(auth_driver).click()                       # same star again clears the rating
    wait(auth_driver).until(lambda d: stars_on(d) == 0)


@pytest.mark.xfail(reason="DEF-008: no recipe details view exists", strict=False)
def test_open_recipe_details(auth_driver):
    open_recipes(auth_driver)
    url = auth_driver.current_url
    all_(auth_driver, ".rcard .recipe-photo")[0].click()
    shown = auth_driver.find_elements(By.CSS_SELECTOR, "[role=dialog], .modal, [class*=detail]")
    assert auth_driver.current_url != url or any(e.is_displayed() for e in shown)


@pytest.mark.skipif(os.environ.get("ALLOW_RECIPE_CREATE") != "1",
                    reason="Recipes are global and cannot be deleted; set ALLOW_RECIPE_CREATE=1")
def test_add_recipe_form(auth_driver):
    open_recipes(auth_driver)
    name = f"QA Selenium Recipe {uuid.uuid4().hex[:6]}"
    type_into(auth_driver, "#new-recipe-name", name)
    type_into(auth_driver, "#new-recipe-ingredients", "tomato, onion")
    type_into(auth_driver, "#new-recipe-instructions", "Chop and cook.")
    visible(auth_driver, "#add-recipe-form button[type=submit]").click()
    wait_for_text(auth_driver, "#api-recipes", name)
