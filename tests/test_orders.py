"""Tests for purchase order placement, status transitions, and inventory effects."""
import pytest
from datetime import datetime, timedelta

from utils.demo_backend import DemoBackend, ServiceError


def future(hours=48):
    return datetime.now() + timedelta(hours=hours)


@pytest.fixture
def be():
    return DemoBackend(seed=False)


@pytest.fixture
def actors(be):
    s = be.register_user("Seller", "s@t.com", "pass1234", "business", "SCo", "Pune")
    b = be.register_user("Buyer",  "b@t.com", "pass1234", "business", "BCo", "Mumbai")
    n = be.register_user("NGO",    "n@t.com", "pass1234", "ngo",      "NGO", "Delhi")
    return s["id"], b["id"], n["id"]


def make_listing(be, seller_id, qty=100, **kw):
    data = dict(name="Onions", category="Vegetables", quantity=qty, unit="kg",
                price=15, original_price=30, condition="Fresh",
                location="Pune", deadline=future(48), description="", donate_if_unsold=False)
    data.update(kw)
    return be.create_listing(seller_id, data)


# ----------------------------------------------------------- place_order
class TestPlaceOrder:
    def test_successful_order_reduces_stock(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s, qty=100)
        o = be.place_order(l["id"], b, 30)
        assert o["status"] == "Pending"
        assert o["quantity"] == 30
        assert be.get_listing(l["id"])["quantity_available"] == 70

    def test_cannot_buy_own_listing(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        with pytest.raises(ServiceError, match="own listing"):
            be.place_order(l["id"], s, 10)

    def test_ngo_cannot_buy(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        with pytest.raises(ServiceError, match="business"):
            be.place_order(l["id"], n, 10)

    def test_exceeding_available_raises(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s, qty=50)
        with pytest.raises(ServiceError, match="available"):
            be.place_order(l["id"], b, 100)

    def test_zero_quantity_raises(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        with pytest.raises(ServiceError, match="greater than zero"):
            be.place_order(l["id"], b, 0)

    def test_cancelled_listing_cannot_be_ordered(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        be.cancel_listing(l["id"], s)
        with pytest.raises(ServiceError, match="cancelled"):
            be.place_order(l["id"], b, 10)

    def test_total_price_calculated(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        o = be.place_order(l["id"], b, 10)
        assert abs(o["total"] - 10 * l["price"]) < 0.01


# ----------------------------------------------------------- set_order_status
class TestOrderStatusTransitions:
    def test_seller_confirms(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        o = be.place_order(l["id"], b, 10)
        result = be.set_order_status(o["id"], s, "Confirmed")
        assert result["status"] == "Confirmed"

    def test_seller_rejects_releases_stock(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s, qty=100)
        o = be.place_order(l["id"], b, 30)
        assert be.get_listing(l["id"])["quantity_available"] == 70
        be.set_order_status(o["id"], s, "Rejected")
        assert be.get_listing(l["id"])["quantity_available"] == 100

    def test_buyer_cancels_pending_releases_stock(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s, qty=100)
        o = be.place_order(l["id"], b, 40)
        assert be.get_listing(l["id"])["quantity_available"] == 60
        be.set_order_status(o["id"], b, "Cancelled")
        assert be.get_listing(l["id"])["quantity_available"] == 100

    def test_buyer_cannot_confirm(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        o = be.place_order(l["id"], b, 10)
        with pytest.raises(ServiceError, match="Cannot change"):
            be.set_order_status(o["id"], b, "Confirmed")

    def test_seller_cannot_skip_to_completed(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        o = be.place_order(l["id"], b, 10)
        with pytest.raises(ServiceError, match="Cannot change"):
            be.set_order_status(o["id"], s, "Completed")

    def test_full_happy_path(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        o = be.place_order(l["id"], b, 10)
        be.set_order_status(o["id"], s, "Confirmed")
        be.set_order_status(o["id"], s, "Ready for collection")
        result = be.set_order_status(o["id"], s, "Completed")
        assert result["status"] == "Completed"
        assert result["completed_at"] is not None

    def test_third_party_cannot_change_status(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        o = be.place_order(l["id"], b, 10)
        stranger = be.register_user("X", "x@t.com", "pass1234", "business", "X", "Pune")
        with pytest.raises(ServiceError, match="not allowed"):
            be.set_order_status(o["id"], stranger["id"], "Confirmed")


# ----------------------------------------------------------- buyer/seller orders
class TestOrderRetrieval:
    def test_buyer_sees_own_orders(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        be.place_order(l["id"], b, 10)
        orders = be.buyer_orders(b)
        assert len(orders) == 1
        assert orders[0]["buyer_id"] == b

    def test_seller_sees_incoming_orders(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        be.place_order(l["id"], b, 10)
        orders = be.seller_orders(s)
        assert len(orders) == 1
        assert orders[0]["seller_id"] == s

    def test_order_dict_has_required_keys(self, be, actors):
        s, b, n = actors
        l = make_listing(be, s)
        o = be.place_order(l["id"], b, 10)
        for key in ("id", "listing_id", "buyer_id", "seller_id", "quantity",
                    "unit_price", "total", "status", "listing_name", "unit",
                    "location", "deadline", "buyer_name", "seller_name"):
            assert key in o, f"Missing key: {key}"
