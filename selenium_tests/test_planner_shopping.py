"""Meal planner (FE-036..045) and shopping list (FE-040..043)."""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from helpers import (accept_alert, all_, body_text, dismiss_alert, maybe_accept_alert,
                     open_page, select_option, type_into, visible, wait, wait_for_text)
from conftest import BASE_URL


# ------------------------------------------------------------------ planner
def meal_selects(driver):
    return all_(driver, "#days select")          # order: Mon B/L/D, Tue B/L/D, ...


def choose(driver, index, label):
    Select(meal_selects(driver)[index]).select_by_visible_text(label)


def selected(driver, index):
    return Select(meal_selects(driver)[index]).first_selected_option.text.strip()


def open_planner(driver):
    open_page(driver, "planner.html")
    wait(driver).until(lambda d: len(meal_selects(d)) == 21)


def test_planner_shows_7_days_and_3_slots(auth_driver):
    open_planner(auth_driver)
    assert len(all_(auth_driver, "#days .day")) == 7
    assert all(len(d.find_elements(By.CSS_SELECTOR, "select")) == 3
               for d in all_(auth_driver, "#days .day"))


def test_add_change_and_remove_meal_updates_totals(auth_driver):
    open_planner(auth_driver)
    choose(auth_driver, 0, "Tomato omelette")                    # FE-036
    wait_for_text(auth_driver, "#wk", "310")
    choose(auth_driver, 1, "Egg fried rice")
    wait_for_text(auth_driver, "#wk", "830")
    choose(auth_driver, 1, "Avocado toast")                      # FE-037
    wait_for_text(auth_driver, "#wk", "650")
    choose(auth_driver, 0, "Choose…")                            # FE-038
    choose(auth_driver, 1, "Choose…")
    wait_for_text(auth_driver, "#wk", "0")


def test_planned_meal_survives_reload(auth_driver):
    open_planner(auth_driver)
    choose(auth_driver, 0, "Tomato omelette")
    wait_for_text(auth_driver, "#wk", "310")
    auth_driver.refresh()
    wait(auth_driver).until(lambda d: len(meal_selects(d)) == 21)
    assert selected(auth_driver, 0) == "Tomato omelette"


def test_auto_generate_and_clear(auth_driver):
    open_planner(auth_driver)
    visible(auth_driver, "#auto").click()
    wait(auth_driver).until(lambda d: all(
        Select(s).first_selected_option.get_attribute("value") for s in meal_selects(d)))
    visible(auth_driver, "#clr").click()
    maybe_accept_alert(auth_driver)
    wait(auth_driver).until(lambda d: not any(
        Select(s).first_selected_option.get_attribute("value") for s in meal_selects(d)))


# ----------------------------------------------------------------- shopping
def shop_cards(driver):
    return all_(driver, "#list .shop-card")


def open_shopping(driver):
    open_page(driver, "shopping.html")
    visible(driver, "#manualShopForm")


def add_shop_item(driver, name, qty="", unit=None):
    type_into(driver, "#nm", name)
    type_into(driver, "#shopQuantity", qty)
    if unit:
        select_option(driver, "#shopUnit", unit)
    visible(driver, "#add").click()


def test_shopping_list_starts_empty(auth_driver):
    open_shopping(auth_driver)
    assert shop_cards(auth_driver) == []


def test_add_manual_item(auth_driver):
    open_shopping(auth_driver)
    add_shop_item(auth_driver, "Basmati rice", "2", "kg")
    wait(auth_driver).until(lambda d: any("basmati rice" in c.text.lower() for c in shop_cards(d)))


def test_blank_name_and_bad_quantity_rejected(auth_driver):
    open_shopping(auth_driver)
    add_shop_item(auth_driver, "", "1")
    wait_for_text(auth_driver, "#shopStatus", "Enter an item name")
    add_shop_item(auth_driver, "Milk", "-1")
    wait_for_text(auth_driver, "#shopStatus", "greater than zero")
    assert shop_cards(auth_driver) == []


def test_duplicate_items_are_combined(auth_driver):
    open_shopping(auth_driver)
    add_shop_item(auth_driver, "Basmati rice", "2", "kg")
    wait(auth_driver).until(lambda d: len(shop_cards(d)) == 1)
    add_shop_item(auth_driver, "basmati rice", "1", "kg")
    wait(auth_driver).until(lambda d: "3 kg" in " ".join(c.text for c in shop_cards(d)))
    assert len(shop_cards(auth_driver)) == 1


def test_mark_purchased_and_delete(auth_driver):
    open_shopping(auth_driver)
    add_shop_item(auth_driver, "Onion", "3")
    wait(auth_driver).until(lambda d: len(shop_cards(d)) == 1)
    visible(auth_driver, "[data-check]").click()
    wait(auth_driver).until(lambda d: "done" in shop_cards(d)[0].get_attribute("class"))
    visible(auth_driver, "[data-delete]").click()
    wait(auth_driver).until(lambda d: len(shop_cards(d)) == 0)


def test_clear_list_cancel_then_confirm(auth_driver):
    open_shopping(auth_driver)
    add_shop_item(auth_driver, "Onion", "1")
    wait(auth_driver).until(lambda d: len(shop_cards(d)) == 1)
    visible(auth_driver, "#clr").click()
    dismiss_alert(auth_driver)
    assert len(shop_cards(auth_driver)) == 1
    visible(auth_driver, "#clr").click()
    accept_alert(auth_driver)
    wait(auth_driver).until(lambda d: len(shop_cards(d)) == 0)


def test_bought_item_moves_to_pantry(auth_driver, api):
    open_shopping(auth_driver)
    add_shop_item(auth_driver, "Oat flour", "1", "kg")
    wait(auth_driver).until(lambda d: len(shop_cards(d)) == 1)
    visible(auth_driver, "[data-check]").click()
    wait(auth_driver).until(lambda d: "done" in shop_cards(d)[0].get_attribute("class"))
    visible(auth_driver, "#mv").click()
    wait(auth_driver).until(lambda d: len(shop_cards(d)) == 0)
    data = api.get(f"{BASE_URL}/api/pantry", timeout=10).json()
    items = data["items"] if isinstance(data, dict) else data
    assert any("oat flour" in i["name"].lower() for i in items)
