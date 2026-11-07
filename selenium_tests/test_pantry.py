"""Pantry page (FE-014 .. FE-023)."""
from selenium.webdriver.common.by import By

from helpers import (accept_alert, all_, body_text, chip_selected, dismiss_alert, open_page,
                     select_option, type_into, visible, wait, wait_for_text)


def cards(driver):
    return all_(driver, "#groups .item")


def names(driver):
    return [c.find_element(By.CSS_SELECTOR, "b").text.lower() for c in cards(driver)]


def add_item(driver, name, qty="1", unit=None):
    type_into(driver, "#name", name)
    type_into(driver, "#qty", qty)
    if unit:
        select_option(driver, "#unit", unit)
    visible(driver, "#addForm button[type=submit]").click()


def card_for(driver, name):
    wait(driver).until(lambda d: name.lower() in names(d))
    return next(c for c in cards(driver)
                if c.find_element(By.CSS_SELECTOR, "b").text.lower() == name.lower())


def test_pantry_page_elements(auth_driver):
    open_page(auth_driver, "pantry.html")
    for css in ("#addForm", "#name", "#qty", "#unit", "#cat", "#exp", "#filter", "#diets"):
        assert visible(auth_driver, css)


def test_add_valid_item(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Red onions")
    card_for(auth_driver, "Red onions")
    wait(auth_driver).until(lambda d: d.find_element(By.ID, "name").get_attribute("value") == "")


def test_add_item_with_quantity_and_unit(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Wheat flour", "2.5", "kg")
    assert "2.5 kg" in card_for(auth_driver, "Wheat flour").text


def test_duplicate_item_is_merged(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Red onions", "1")
    card_for(auth_driver, "Red onions")
    add_item(auth_driver, "red ONIONS", "2")
    wait_for_text(auth_driver, "#pantryToast", "Added to the amount you already have")
    assert names(auth_driver).count("red onions") == 1
    assert "3 pcs" in card_for(auth_driver, "Red onions").text


def test_empty_name_is_blocked(auth_driver):
    open_page(auth_driver, "pantry.html")
    type_into(auth_driver, "#name", "")
    visible(auth_driver, "#addForm button[type=submit]").click()
    assert auth_driver.execute_script("return document.getElementById('name').validity.valueMissing")
    assert cards(auth_driver) == []


def test_spaces_only_name_rejected(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "   ")
    wait_for_text(auth_driver, "#pantryToast", "Enter an item name")
    assert cards(auth_driver) == []


def test_zero_and_negative_amount_rejected(auth_driver):
    open_page(auth_driver, "pantry.html")
    for bad in ("0", "-1"):
        add_item(auth_driver, "Bad amount", bad)
    assert cards(auth_driver) == []


def test_edit_item_amount(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Carrots")
    card = card_for(auth_driver, "Carrots")
    card.find_element(By.CSS_SELECTOR, "[data-ed]").click()
    accept_alert(auth_driver, "4")          # prompt 1: amount (text is replaced)
    accept_alert(auth_driver)               # prompt 2: expiry, keep empty
    wait(auth_driver).until(lambda d: "4 pcs" in card_for(d, "Carrots").text)


def test_edit_item_invalid_amount_keeps_value(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Carrots", "2")
    card_for(auth_driver, "Carrots").find_element(By.CSS_SELECTOR, "[data-ed]").click()
    accept_alert(auth_driver, "abc")
    accept_alert(auth_driver)
    wait_for_text(auth_driver, "#pantryToast", "number")
    assert "2 pcs" in card_for(auth_driver, "Carrots").text


def test_plus_minus_buttons(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Eggs", "1")
    card_for(auth_driver, "Eggs").find_element(By.CSS_SELECTOR, "[data-p]").click()
    wait(auth_driver).until(lambda d: "2 pcs" in card_for(d, "Eggs").text)
    card_for(auth_driver, "Eggs").find_element(By.CSS_SELECTOR, "[data-m]").click()
    wait(auth_driver).until(lambda d: "1 pcs" in card_for(d, "Eggs").text)


def test_delete_item(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Wheat flour")
    card_for(auth_driver, "Wheat flour").find_element(By.CSS_SELECTOR, "[data-rm]").click()
    wait(auth_driver).until(lambda d: "wheat flour" not in names(d))


def test_clear_all_cancel_then_confirm(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Rice")
    add_item(auth_driver, "Beans")
    wait(auth_driver).until(lambda d: len(cards(d)) == 2)
    visible(auth_driver, "#clear").click()
    assert "Remove all pantry items" in dismiss_alert(auth_driver)
    assert len(cards(auth_driver)) == 2
    visible(auth_driver, "#clear").click()
    accept_alert(auth_driver)
    wait(auth_driver).until(lambda d: len(cards(d)) == 0)
    assert "pantry is empty" in body_text(auth_driver).lower()


def test_filter_ingredients(auth_driver):
    open_page(auth_driver, "pantry.html")
    add_item(auth_driver, "Onion")
    add_item(auth_driver, "Carrot")
    wait(auth_driver).until(lambda d: len(cards(d)) == 2)
    type_into(auth_driver, "#filter", "oni")
    wait(auth_driver).until(lambda d: "carrot" not in " ".join(
        c.text.lower() for c in cards(d) if c.is_displayed()))
    assert "onion" in body_text(auth_driver).lower()


def test_dietary_chip_persists_after_reload(auth_driver):
    open_page(auth_driver, "pantry.html")
    chip = visible(auth_driver, "#diets [data-d='Vegan']")
    chip.click()
    wait(auth_driver).until(lambda d: chip_selected(d.find_element(
        By.CSS_SELECTOR, "#diets [data-d='Vegan']")))
    auth_driver.refresh()
    chip = visible(auth_driver, "#diets [data-d='Vegan']")
    assert chip_selected(chip)
    chip.click()                                    # deselect again
    wait(auth_driver).until(lambda d: not chip_selected(d.find_element(
        By.CSS_SELECTOR, "#diets [data-d='Vegan']")))
