
"""Tests for FoodBridge donation workflows and eligibility."""

import unittest
from datetime import datetime, timedelta

import pytest

from utils.demo_backend import DemoBackend, ServiceError, DONATION_WINDOW_HOURS
from logic.donation_logic import (
    check_donation_eligibility,
    update_donation_status,
)


def future(hours):
    return datetime.now() + timedelta(hours=hours)


@pytest.fixture
def be():
    return DemoBackend(seed=False)


@pytest.fixture
def actors(be):
    seller = be.register_user(
        "Seller", "s@t.com", "pass1234", "business", "SCo", "Pune"
    )
    ngo = be.register_user(
        "NGO", "n@t.com", "pass1234", "ngo", "NGO", "Delhi"
    )
    buyer = be.register_user(
        "Buyer", "b@t.com", "pass1234", "business", "BCo", "Mumbai"
    )
    return seller["id"], ngo["id"], buyer["id"]


def make_donatable(be, seller_id, qty=50, deadline_hours=24):
    """Create a listing eligible for donation."""
    return be.create_listing(
        seller_id,
        dict(
            name="Spinach",
            category="Vegetables",
            quantity=qty,
            unit="kg",
            price=10,
            original_price=20,
            condition="Best used soon",
            location="Pune",
            deadline=future(deadline_hours),
            description="",
            donate_if_unsold=True,
        ),
    )


def make_non_donatable(be, seller_id, qty=50):
    """Create a listing not eligible for donation."""
    return be.create_listing(
        seller_id,
        dict(
            name="Rice",
            category="Grains & Pulses",
            quantity=qty,
            unit="kg",
            price=50,
            original_price=80,
            condition="Good",
            location="Pune",
            deadline=future(200),
            description="",
            donate_if_unsold=False,
        ),
    )


class TestDonationEligibility:
    def test_near_deadline_with_donate_flag_is_eligible(self, be, actors):
        seller_id, _, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        assert be.get_listing(listing["id"])["donation_eligible"] is True

    def test_far_deadline_is_not_eligible(self, be, actors):
        seller_id, _, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS + 50
        )
        assert be.get_listing(listing["id"])["donation_eligible"] is False

    def test_no_donate_flag_is_not_eligible(self, be, actors):
        seller_id, _, _ = actors
        listing = make_non_donatable(be, seller_id)
        assert be.get_listing(listing["id"])["donation_eligible"] is False

    def test_donation_offers_only_eligible(self, be, actors):
        seller_id, _, _ = actors
        eligible = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        non_eligible = make_non_donatable(be, seller_id)

        offers = be.donation_offers()
        ids = [offer["id"] for offer in offers]

        assert eligible["id"] in ids
        assert non_eligible["id"] not in ids


class TestRequestDonation:
    def test_ngo_can_request(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )

        donation = be.request_donation(listing["id"], ngo_id, 10)

        assert donation["status"] == "Requested"
        assert donation["quantity"] == 10
        assert be.get_listing(listing["id"])["quantity_available"] == 40

    def test_business_cannot_request_donation(self, be, actors):
        seller_id, _, buyer_id = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )

        with pytest.raises(ServiceError, match="NGOs"):
            be.request_donation(listing["id"], buyer_id, 5)

    def test_non_eligible_listing_raises(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_non_donatable(be, seller_id)

        with pytest.raises(ServiceError, match="not currently available"):
            be.request_donation(listing["id"], ngo_id, 5)

    def test_exceeding_available_raises(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, qty=20,
            deadline_hours=DONATION_WINDOW_HOURS - 1,
        )

        with pytest.raises(ServiceError, match="available"):
            be.request_donation(listing["id"], ngo_id, 50)

    def test_zero_quantity_raises(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )

        with pytest.raises(ServiceError, match="greater than zero"):
            be.request_donation(listing["id"], ngo_id, 0)


class TestDonationStatusTransitions:
    def test_seller_approves(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 10)

        result = be.set_donation_status(donation["id"], seller_id, "Approved")
        assert result["status"] == "Approved"

    def test_seller_declines_releases_stock(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 20)

        assert be.get_listing(listing["id"])["quantity_available"] == 30
        be.set_donation_status(donation["id"], seller_id, "Declined")
        assert be.get_listing(listing["id"])["quantity_available"] == 50

    def test_ngo_can_cancel_requested(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 10)

        result = be.set_donation_status(donation["id"], ngo_id, "Cancelled")
        assert result["status"] == "Cancelled"
        assert be.get_listing(listing["id"])["quantity_available"] == 50

    def test_ngo_can_cancel_approved(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 10)
        be.set_donation_status(donation["id"], seller_id, "Approved")

        result = be.set_donation_status(donation["id"], ngo_id, "Cancelled")
        assert result["status"] == "Cancelled"

    def test_seller_marks_collected(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 10)
        be.set_donation_status(donation["id"], seller_id, "Approved")

        result = be.set_donation_status(donation["id"], seller_id, "Collected")
        assert result["status"] == "Collected"
        assert result["completed_at"] is not None

    def test_invalid_transition_raises(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 10)

        with pytest.raises(ServiceError, match="Cannot change"):
            be.set_donation_status(donation["id"], seller_id, "Collected")

    def test_third_party_cannot_change(self, be, actors):
        seller_id, ngo_id, buyer_id = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 10)

        with pytest.raises(ServiceError, match="not allowed"):
            be.set_donation_status(donation["id"], buyer_id, "Approved")


class TestDonationRetrieval:
    def test_ngo_requests_returns_own(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        be.request_donation(listing["id"], ngo_id, 10)

        requests = be.ngo_requests(ngo_id)
        assert len(requests) == 1
        assert requests[0]["ngo_id"] == ngo_id

    def test_seller_donation_requests(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        be.request_donation(listing["id"], ngo_id, 5)

        requests = be.seller_donation_requests(seller_id)
        assert len(requests) == 1
        assert requests[0]["seller_id"] == seller_id

    def test_donation_dict_has_required_keys(self, be, actors):
        seller_id, ngo_id, _ = actors
        listing = make_donatable(
            be, seller_id, deadline_hours=DONATION_WINDOW_HOURS - 1
        )
        donation = be.request_donation(listing["id"], ngo_id, 5)

        required_keys = (
            "id", "listing_id", "ngo_id", "seller_id", "quantity",
            "status", "listing_name", "unit", "location", "deadline",
            "ngo_name", "seller_name",
        )
        for key in required_keys:
            assert key in donation, f"Missing key: {key}"


class TestStandaloneDonationLogic(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now()
        self.deadline = self.now + timedelta(hours=2)

    def test_eligible_ingredient(self):
        result, message = check_donation_eligibility(
            5, "fresh", self.deadline, self.now, True
        )
        self.assertTrue(result)

    def test_spoiled_ingredient_rejected(self):
        result, message = check_donation_eligibility(
            5, "spoiled", self.deadline, self.now, True
        )
        self.assertFalse(result)

    def test_unverified_ingredient_rejected(self):
        result, message = check_donation_eligibility(
            5, "fresh", self.deadline, self.now, False
        )
        self.assertFalse(result)

    def test_zero_quantity_rejected(self):
        result, message = check_donation_eligibility(
            0, "fresh", self.deadline, self.now, True
        )
        self.assertFalse(result)

    def test_expired_deadline_rejected(self):
        result, message = check_donation_eligibility(
            5, "fresh", self.now - timedelta(minutes=1), self.now, True
        )
        self.assertFalse(result)

    def test_pending_donation_can_be_accepted(self):
        self.assertEqual(
            update_donation_status("pending", "accepted"), "accepted"
        )

    def test_collected_donation_cannot_be_accepted_again(self):
        with self.assertRaises(ValueError):
            update_donation_status("collected", "accepted")
