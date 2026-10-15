"""Frontend tests: backend contract used by the UI, plus headless runs of the Streamlit screens."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from utils.demo_backend import DemoBackend, ServiceError


MAIN = Path(__file__).resolve().parent.parent / "main.py"


@pytest.fixture(autouse=True)
def fresh_backend():
    st.cache_resource.clear()


def app():
    at = AppTest.from_file(str(MAIN), default_timeout=30)
    at.run()
    return at


def sign_in(at, email="buyer@demo.com", password="demo1234"):
    at.text_input[0].set_value(email)
    at.text_input[1].set_value(password)
    at.button[0].click().run()   # first button = form submit
    return at


def texts(at):
    return " ".join(m.value for m in at.markdown) + " ".join(e.value for e in at.error)


# ----------------------------------------------------------------- screens
def test_login_screen_displays():
    at = app()
    assert at.subheader[0].value == "Sign in"
    assert [t.label for t in at.text_input] == ["Email", "Password"]


def test_login_required_fields_cannot_be_empty():
    at = app()
    at.button[0].click().run()
    msgs = [e.value for e in at.error]
    assert "Email is required." in msgs and "Password is required." in msgs


def test_wrong_password_shows_error():
    at = sign_in(app(), password="nope")
    assert any("Incorrect email or password" in e.value for e in at.error)


def test_register_screen_required_fields():
    at = app()
    next(b for b in at.button if "Create an account" in b.label).click().run()
    assert at.subheader[0].value == "Create your account"
    at.button[0].click().run()
    msgs = [e.value for e in at.error]
    for label in ("Organisation name", "Your name", "Email", "Location", "Password", "Confirm password"):
        assert f"{label} is required." in msgs


def test_marketplace_displays_ingredients_and_search_filters():
    at = sign_in(app())
    assert at.title[0].value == "Marketplace"
    assert "Tomatoes" in texts(at) and "Fresh paneer" in texts(at)
    at.text_input(key="mk_query").set_value("paneer").run()
    body = texts(at)
    assert "Fresh paneer" in body and "Tomatoes" not in body


def test_ngo_sees_donation_offers():
    at = sign_in(app(), "ngo@demo.com")
    assert at.title[0].value == "Donation offers"
    body = texts(at)
    assert "Fresh paneer" in body and "Spinach" in body and "Tomatoes" not in body


def test_impact_dashboard_renders():
    at = sign_in(app())
    next(b for b in at.button if "Impact" in b.label).click().run()
    assert at.title[0].value == "Impact"
    assert not at.exception


# ----------------------------------------------------------- backend contract
def test_search_and_filters_by_price_quantity_location():
    be = DemoBackend()
    assert [l["name"] for l in be.search_listings(query="tomato")] == ["Tomatoes"]
    assert all(l["price"] <= 20 for l in be.search_listings(max_price=20))
    assert all(l["quantity_available"] >= 100 for l in be.search_listings(min_quantity=100))
    assert all("kothrud" in l["location"].lower() for l in be.search_listings(location="Kothrud"))
    assert be.search_listings(query="zzz") == []


def test_cancelled_listing_leaves_marketplace_and_cancels_orders():
    be = DemoBackend()
    seller = be.authenticate("seller@demo.com", "demo1234")["id"]
    tomatoes = next(l for l in be.seller_listings(seller) if l["name"] == "Tomatoes")
    be.cancel_listing(tomatoes["id"], seller)
    assert "Tomatoes" not in [l["name"] for l in be.search_listings()]
    assert be.get_listing(tomatoes["id"])["status"] == "Cancelled"
    assert all(o["status"] == "Cancelled" for o in be.seller_orders(seller) if o["listing_name"] == "Tomatoes")


def test_edit_listing_and_reserved_stock_guard():
    be = DemoBackend()
    seller = be.authenticate("seller@demo.com", "demo1234")["id"]
    t = next(l for l in be.seller_listings(seller) if l["name"] == "Tomatoes")   # 15 kg reserved
    data = {k: t[k] for k in ("name", "category", "unit", "price", "original_price", "condition", "location",
                              "deadline", "description", "donate_if_unsold")}
    assert be.update_listing(t["id"], seller, {**data, "quantity": 200})["quantity_available"] == 185
    with pytest.raises(ServiceError):
        be.update_listing(t["id"], seller, {**data, "quantity": 10})


def test_buyer_purchase_request_and_status_flow():
    be = DemoBackend()
    buyer = be.authenticate("buyer@demo.com", "demo1234")["id"]
    seller = be.authenticate("bakery@demo.com", "demo1234")["id"]
    onions = next(l for l in be.search_listings() if l["name"] == "Onions")
    order = be.place_order(onions["id"], buyer, 10)
    assert order["status"] == "Pending"
    assert be.get_listing(onions["id"])["quantity_available"] == onions["quantity_available"] - 10
    assert be.set_order_status(order["id"], seller, "Confirmed")["status"] == "Confirmed"
    assert be.set_order_status(order["id"], buyer, "Cancelled")["status"] == "Cancelled"
    assert be.get_listing(onions["id"])["quantity_available"] == onions["quantity_available"]   # stock released
    with pytest.raises(ServiceError):
        be.place_order(onions["id"], buyer, 10_000)
    with pytest.raises(ServiceError):
        be.place_order(onions["id"], seller, 1)   # own listing


def test_listing_validation_rejects_bad_input():
    be = DemoBackend()
    seller = be.authenticate("seller@demo.com", "demo1234")["id"]
    with pytest.raises(ServiceError) as err:
        be.create_listing(seller, dict(name="", quantity=0, price=-1, location="", deadline=datetime.now() - timedelta(hours=1)))
    assert "Ingredient name is required" in str(err.value) and "future" in str(err.value)


def test_impact_stats_update_after_transaction():
    be = DemoBackend()
    before = be.impact_stats()
    buyer = be.authenticate("buyer@demo.com", "demo1234")["id"]
    seller = be.authenticate("bakery@demo.com", "demo1234")["id"]
    onions = next(l for l in be.search_listings() if l["name"] == "Onions")
    o = be.place_order(onions["id"], buyer, 25)
    for status in ("Confirmed", "Ready for collection", "Completed"):
        be.set_order_status(o["id"], seller, status)
    after = be.impact_stats()
    assert after["resold_kg"] == before["resold_kg"] + 25
    assert after["orders_completed"] == before["orders_completed"] + 1


@pytest.mark.parametrize("email", ["seller@demo.com", "buyer@demo.com", "ngo@demo.com"])
def test_every_screen_renders_without_errors(email):
    at = sign_in(app(), email)
    labels = [b.label for b in at.button if b.key and b.key.startswith("nav_")]
    assert labels
    for label in labels:
        next(b for b in at.button if b.label == label).click().run()
        assert not at.exception, f"{label} raised {at.exception}"


def test_seller_can_open_listing_editor():
    at = sign_in(app(), "seller@demo.com")
    next(b for b in at.button if "Seller dashboard" in b.label).click().run()
    next(b for b in at.button if b.label == "Edit").click().run()
    assert at.title[0].value == "Edit listing"
    assert not at.exception


def test_listing_form_blocks_empty_required_fields():
    at = sign_in(app(), "seller@demo.com")
    next(b for b in at.button if "Seller dashboard" in b.label).click().run()
    next(b for b in at.button if "Add surplus" in b.label).click().run()
    next(b for b in at.button if b.label == "Publish listing").click().run()
    msgs = [e.value for e in at.error]
    assert "Ingredient name is required." in msgs and "Quantity must be greater than zero." in msgs
