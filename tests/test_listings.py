
"""Tests for FoodBridge listing workflows and shared validation."""

import pytest
from datetime import datetime, timedelta

from utils.demo_backend import DemoBackend, ServiceError
from logic.validation import validate_listing


def future(hours=48):
    return datetime.now() + timedelta(hours=hours)


@pytest.fixture
def be():
    return DemoBackend(seed=False)


@pytest.fixture
def setup(be):
    seller = be.register_user(
        "Seller", "seller@t.com", "pass1234", "business", "SellerCo", "Pune"
    )
    buyer = be.register_user(
        "Buyer", "buyer@t.com", "pass1234", "business", "BuyerCo", "Mumbai"
    )
    ngo = be.register_user(
        "NGO", "ngo@t.com", "pass1234", "ngo", "NGO Corp", "Delhi"
    )
    return seller["id"], buyer["id"], ngo["id"]


def _listing_data(**overrides):
    defaults = dict(
        name="Tomatoes",
        category="Vegetables",
        quantity=100,
        unit="kg",
        price=10,
        original_price=20,
        condition="Fresh",
        location="Pune",
        deadline=future(48),
        description="",
        donate_if_unsold=False,
    )
    defaults.update(overrides)
    return defaults


class TestCreateListing:
    def test_business_can_create_listing(self, be, setup):
        seller_id, *_ = setup
        listing = be.create_listing(seller_id, _listing_data())
        assert listing["name"] == "Tomatoes"
        assert listing["status"] == "Available"
        assert listing["quantity_available"] == 100

    def test_ngo_cannot_create_listing(self, be, setup):
        _, _, ngo_id = setup
        with pytest.raises(ServiceError, match="business"):
            be.create_listing(ngo_id, _listing_data())

    def test_empty_name_raises(self, be, setup):
        seller_id, *_ = setup
        with pytest.raises(ServiceError, match="Ingredient name"):
            be.create_listing(seller_id, _listing_data(name=""))

    def test_zero_quantity_raises(self, be, setup):
        seller_id, *_ = setup
        with pytest.raises(ServiceError, match="Quantity"):
            be.create_listing(seller_id, _listing_data(quantity=0))

    def test_past_deadline_raises(self, be, setup):
        seller_id, *_ = setup
        with pytest.raises(ServiceError, match="future"):
            be.create_listing(
                seller_id,
                _listing_data(deadline=datetime.now() - timedelta(hours=1)),
            )

    def test_original_price_below_discounted_raises(self, be, setup):
        seller_id, *_ = setup
        with pytest.raises(ServiceError, match="lower"):
            be.create_listing(
                seller_id, _listing_data(price=50, original_price=10)
            )

    def test_discount_pct_calculated(self, be, setup):
        seller_id, *_ = setup
        listing = be.create_listing(
            seller_id, _listing_data(price=10, original_price=20)
        )
        assert listing["discount_pct"] == 50

    def test_invalid_category_raises(self, be, setup):
        seller_id, *_ = setup
        with pytest.raises(ServiceError, match="category"):
            be.create_listing(seller_id, _listing_data(category="Junk"))


class TestUpdateListing:
    def test_update_quantity_up(self, be, setup):
        seller_id, _, _ = setup
        listing = be.create_listing(seller_id, _listing_data(quantity=100))
        updated = be.update_listing(
            listing["id"], seller_id, _listing_data(quantity=200)
        )
        assert updated["quantity"] == 200
        assert updated["quantity_available"] == 200

    def test_cannot_reduce_below_reserved(self, be, setup):
        seller_id, buyer_id, _ = setup
        listing = be.create_listing(seller_id, _listing_data(quantity=100))
        be.place_order(listing["id"], buyer_id, 50)
        with pytest.raises(ServiceError, match="reserved"):
            be.update_listing(
                listing["id"], seller_id, _listing_data(quantity=30)
            )

    def test_cannot_edit_cancelled_listing(self, be, setup):
        seller_id, *_ = setup
        listing = be.create_listing(seller_id, _listing_data())
        be.cancel_listing(listing["id"], seller_id)
        with pytest.raises(ServiceError, match="cancelled"):
            be.update_listing(listing["id"], seller_id, _listing_data())

    def test_other_seller_cannot_edit(self, be, setup):
        seller_id, buyer_id, _ = setup
        listing = be.create_listing(seller_id, _listing_data())
        with pytest.raises(ServiceError, match="own"):
            be.update_listing(listing["id"], buyer_id, _listing_data())


class TestCancelListing:
    def test_cancel_removes_from_marketplace(self, be, setup):
        seller_id, *_ = setup
        listing = be.create_listing(seller_id, _listing_data())
        be.cancel_listing(listing["id"], seller_id)
        assert be.get_listing(listing["id"])["status"] == "Cancelled"
        assert listing["name"] not in [
            item["name"] for item in be.search_listings()
        ]

    def test_cancel_cascades_to_orders(self, be, setup):
        seller_id, buyer_id, _ = setup
        listing = be.create_listing(seller_id, _listing_data())
        be.place_order(listing["id"], buyer_id, 10)
        be.cancel_listing(listing["id"], seller_id)
        assert be.seller_orders(seller_id)[0]["status"] == "Cancelled"

    def test_double_cancel_raises(self, be, setup):
        seller_id, *_ = setup
        listing = be.create_listing(seller_id, _listing_data())
        be.cancel_listing(listing["id"], seller_id)
        with pytest.raises(ServiceError, match="already cancelled"):
            be.cancel_listing(listing["id"], seller_id)


class TestSearchListings:
    def test_search_by_name(self, be, setup):
        seller_id, *_ = setup
        be.create_listing(seller_id, _listing_data(name="Tomatoes"))
        be.create_listing(seller_id, _listing_data(name="Onions"))
        results = be.search_listings(query="tomato")
        assert [item["name"] for item in results] == ["Tomatoes"]

    def test_filter_by_max_price(self, be, setup):
        seller_id, *_ = setup
        be.create_listing(
            seller_id, _listing_data(name="Cheap", price=5, original_price=10)
        )
        be.create_listing(
            seller_id,
            _listing_data(name="Expensive", price=100, original_price=120),
        )
        results = be.search_listings(max_price=10)
        assert all(item["price"] <= 10 for item in results)

    def test_filter_by_location(self, be, setup):
        seller_id, *_ = setup
        be.create_listing(
            seller_id, _listing_data(name="Pune Item", location="Kothrud, Pune")
        )
        be.create_listing(
            seller_id,
            _listing_data(name="Mumbai Item", location="Bandra, Mumbai"),
        )
        results = be.search_listings(location="Pune")
        assert all("Pune" in item["location"] for item in results)

    def test_cancelled_not_in_results(self, be, setup):
        seller_id, *_ = setup
        listing = be.create_listing(seller_id, _listing_data())
        be.cancel_listing(listing["id"], seller_id)
        assert listing["name"] not in [
            item["name"] for item in be.search_listings()
        ]

    def test_no_results_for_unknown_query(self, be, setup):
        seller_id, *_ = setup
        be.create_listing(seller_id, _listing_data())
        assert be.search_listings(query="zzz") == []


class TestSharedListingValidation:
    def test_valid_listing(self):
        clean = validate_listing(_listing_data())
        assert clean["name"] == "Tomatoes"
        assert clean["quantity"] == 100

    def test_empty_name_rejected(self):
        with pytest.raises(ServiceError, match="Ingredient name"):
            validate_listing(_listing_data(name=" "))

    def test_zero_quantity_rejected(self):
        with pytest.raises(ServiceError, match="Quantity"):
            validate_listing(_listing_data(quantity=0))

    def test_negative_price_rejected(self):
        with pytest.raises(ServiceError, match="Price"):
            validate_listing(_listing_data(price=-5))

    def test_discounted_price_above_original_rejected(self):
        with pytest.raises(ServiceError, match="lower"):
            validate_listing(_listing_data(price=50, original_price=40))

    def test_past_deadline_rejected(self):
        with pytest.raises(ServiceError, match="future"):
            validate_listing(
                _listing_data(deadline=datetime.now() - timedelta(hours=1))
            )

    def test_spoiled_condition_rejected(self):
        with pytest.raises(ServiceError, match="condition"):
            validate_listing(_listing_data(condition="spoiled"))

    def test_missing_location_rejected(self):
        with pytest.raises(ServiceError, match="Location"):
            validate_listing(_listing_data(location=" "))
