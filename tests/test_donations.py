"""Tests for NGO donation requests, status transitions, and eligibility."""
import pytest
from datetime import datetime, timedelta

from utils.demo_backend import DemoBackend, ServiceError, DONATION_WINDOW_HOURS


def future(hours):
    return datetime.now() + timedelta(hours=hours)


@pytest.fixture
def be():
    return DemoBackend(seed=False)


@pytest.fixture
def actors(be):
    s = be.register_user("Seller", "s@t.com", "pass1234", "business", "SCo", "Pune")
    n = be.register_user("NGO",    "n@t.com", "pass1234", "ngo",      "NGO", "Delhi")
    b = be.register_user("Buyer",  "b@t.com", "pass1234", "business", "BCo", "Mumbai")
    return s["id"], n["id"], b["id"]


def make_donatable(be, seller_id, qty=50, deadline_hours=24):
    """Create a listing eligible for donation."""
    return be.create_listing(seller_id, dict(
        name="Spinach", category="Vegetables", quantity=qty, unit="kg",
        price=10, original_price=20, condition="Best used soon",
        location="Pune", deadline=future(deadline_hours),
        description="", donate_if_unsold=True,
    ))


def make_non_donatable(be, seller_id, qty=50):
    return be.create_listing(seller_id, dict(
        name="Rice", category="Grains & Pulses", quantity=qty, unit="kg",
        price=50, original_price=80, condition="Good",
        location="Pune", deadline=future(200),
        description="", donate_if_unsold=False,
    ))


# ----------------------------------------------------------- eligibility
class TestDonationEligibility:
    def test_near_deadline_with_donate_flag_is_eligible(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        assert be.get_listing(l["id"])["donation_eligible"] is True

    def test_far_deadline_is_not_eligible(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS + 50)
        assert be.get_listing(l["id"])["donation_eligible"] is False

    def test_no_donate_flag_is_not_eligible(self, be, actors):
        s, n, b = actors
        l = make_non_donatable(be, s)
        assert be.get_listing(l["id"])["donation_eligible"] is False

    def test_donation_offers_only_eligible(self, be, actors):
        s, n, b = actors
        eligible = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        non_eligible = make_non_donatable(be, s)
        offers = be.donation_offers()
        ids = [o["id"] for o in offers]
        assert eligible["id"] in ids
        assert non_eligible["id"] not in ids


# ----------------------------------------------------------- request_donation
class TestRequestDonation:
    def test_ngo_can_request(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 10)
        assert d["status"] == "Requested"
        assert d["quantity"] == 10
        assert be.get_listing(l["id"])["quantity_available"] == 40

    def test_business_cannot_request_donation(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        with pytest.raises(ServiceError, match="NGOs"):
            be.request_donation(l["id"], b, 5)

    def test_non_eligible_listing_raises(self, be, actors):
        s, n, b = actors
        l = make_non_donatable(be, s)
        with pytest.raises(ServiceError, match="not currently available"):
            be.request_donation(l["id"], n, 5)

    def test_exceeding_available_raises(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, qty=20, deadline_hours=DONATION_WINDOW_HOURS - 1)
        with pytest.raises(ServiceError, match="available"):
            be.request_donation(l["id"], n, 50)

    def test_zero_quantity_raises(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        with pytest.raises(ServiceError, match="greater than zero"):
            be.request_donation(l["id"], n, 0)


# ----------------------------------------------------------- status transitions
class TestDonationStatusTransitions:
    def test_seller_approves(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 10)
        result = be.set_donation_status(d["id"], s, "Approved")
        assert result["status"] == "Approved"

    def test_seller_declines_releases_stock(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, qty=50, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 20)
        assert be.get_listing(l["id"])["quantity_available"] == 30
        be.set_donation_status(d["id"], s, "Declined")
        assert be.get_listing(l["id"])["quantity_available"] == 50

    def test_ngo_can_cancel_requested(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, qty=50, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 10)
        result = be.set_donation_status(d["id"], n, "Cancelled")
        assert result["status"] == "Cancelled"
        assert be.get_listing(l["id"])["quantity_available"] == 50

    def test_ngo_can_cancel_approved(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, qty=50, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 10)
        be.set_donation_status(d["id"], s, "Approved")
        result = be.set_donation_status(d["id"], n, "Cancelled")
        assert result["status"] == "Cancelled"

    def test_seller_marks_collected(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 10)
        be.set_donation_status(d["id"], s, "Approved")
        result = be.set_donation_status(d["id"], s, "Collected")
        assert result["status"] == "Collected"
        assert result["completed_at"] is not None

    def test_invalid_transition_raises(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 10)
        with pytest.raises(ServiceError, match="Cannot change"):
            be.set_donation_status(d["id"], s, "Collected")  # must approve first

    def test_third_party_cannot_change(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 10)
        with pytest.raises(ServiceError, match="not allowed"):
            be.set_donation_status(d["id"], b, "Approved")


# ----------------------------------------------------------- retrieval
class TestDonationRetrieval:
    def test_ngo_requests_returns_own(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        be.request_donation(l["id"], n, 10)
        reqs = be.ngo_requests(n)
        assert len(reqs) == 1 and reqs[0]["ngo_id"] == n

    def test_seller_donation_requests(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        be.request_donation(l["id"], n, 5)
        reqs = be.seller_donation_requests(s)
        assert len(reqs) == 1 and reqs[0]["seller_id"] == s

    def test_donation_dict_has_required_keys(self, be, actors):
        s, n, b = actors
        l = make_donatable(be, s, deadline_hours=DONATION_WINDOW_HOURS - 1)
        d = be.request_donation(l["id"], n, 5)
        for key in ("id", "listing_id", "ngo_id", "seller_id", "quantity",
                    "status", "listing_name", "unit", "location", "deadline",
                    "ngo_name", "seller_name"):
            assert key in d, f"Missing key: {key}"
