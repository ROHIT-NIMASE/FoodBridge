"""Tests for matching and search logic (pure Python, no DB)."""
import pytest
from datetime import datetime, timedelta

from logic.matching_logic import match_listings_to_query, eligible_donation_listings
from logic.donation_logic import is_donation_eligible
from logic.pricing_logic import discount_percentage, savings_amount
from logic.expiry_logic import is_expired


def future(hours=48):
    return datetime.now() + timedelta(hours=hours)


def make_view(**overrides):
    """Create a minimal listing view dict."""
    v = dict(
        id=1, name="Tomatoes", category="Vegetables",
        description="", price=10, quantity_available=100,
        condition="Fresh", location="Pune",
        deadline=future(48), status="Available",
        donate_if_unsold=False, donation_eligible=False,
        discount_pct=50, original_price=20,
    )
    v.update(overrides)
    return v


# ----------------------------------------------------------- match_listings_to_query
class TestMatchListingsToQuery:
    def test_query_filters_by_name(self):
        listings = [make_view(name="Tomatoes"), make_view(name="Onions")]
        result = match_listings_to_query(listings, query="tomato")
        assert [l["name"] for l in result] == ["Tomatoes"]

    def test_query_filters_by_description(self):
        listings = [make_view(description="ripe bananas"), make_view(description="raw onions")]
        result = match_listings_to_query(listings, query="banana")
        assert len(result) == 1

    def test_location_filter(self):
        listings = [make_view(location="Kothrud, Pune"), make_view(location="Bandra, Mumbai")]
        result = match_listings_to_query(listings, location="Pune")
        assert len(result) == 1

    def test_category_filter(self):
        listings = [make_view(category="Vegetables"), make_view(category="Dairy & Eggs")]
        result = match_listings_to_query(listings, category="Vegetables")
        assert len(result) == 1

    def test_condition_filter(self):
        listings = [make_view(condition="Fresh"), make_view(condition="Good")]
        result = match_listings_to_query(listings, conditions=["Fresh"])
        assert len(result) == 1

    def test_min_price_filter(self):
        listings = [make_view(price=5), make_view(price=20)]
        result = match_listings_to_query(listings, min_price=10)
        assert all(l["price"] >= 10 for l in result)

    def test_max_price_filter(self):
        listings = [make_view(price=5), make_view(price=20)]
        result = match_listings_to_query(listings, max_price=10)
        assert all(l["price"] <= 10 for l in result)

    def test_min_quantity_filter(self):
        listings = [make_view(quantity_available=10), make_view(quantity_available=200)]
        result = match_listings_to_query(listings, min_quantity=100)
        assert all(l["quantity_available"] >= 100 for l in result)

    def test_non_available_excluded(self):
        listings = [make_view(status="Cancelled"), make_view(status="Available", name="Good")]
        result = match_listings_to_query(listings)
        assert [l["name"] for l in result] == ["Good"]

    def test_sort_by_price_low_to_high(self):
        listings = [make_view(price=30), make_view(price=5), make_view(price=15)]
        result = match_listings_to_query(listings, sort="Price: low to high")
        assert result[0]["price"] <= result[-1]["price"]

    def test_sort_biggest_discount(self):
        listings = [make_view(discount_pct=10), make_view(discount_pct=80)]
        result = match_listings_to_query(listings, sort="Biggest discount")
        assert result[0]["discount_pct"] >= result[-1]["discount_pct"]

    def test_empty_results(self):
        listings = [make_view()]
        assert match_listings_to_query(listings, query="xyznotfound") == []


# ----------------------------------------------------------- donation eligibility
class TestEligibleDonationListings:
    def test_eligible_appear(self):
        listings = [
            make_view(donation_eligible=True),
            make_view(donation_eligible=False),
        ]
        result = eligible_donation_listings(listings)
        assert len(result) == 1

    def test_sorted_by_deadline(self):
        listings = [
            make_view(donation_eligible=True, deadline=future(30), name="B"),
            make_view(donation_eligible=True, deadline=future(5), name="A"),
        ]
        result = eligible_donation_listings(listings)
        assert result[0]["name"] == "A"


# ----------------------------------------------------------- is_donation_eligible
class TestIsDonationEligible:
    def test_eligible(self):
        l = make_view(status="Available", donate_if_unsold=True, deadline=future(10))
        assert is_donation_eligible(l) is True

    def test_far_deadline_not_eligible(self):
        l = make_view(status="Available", donate_if_unsold=True, deadline=future(200))
        assert is_donation_eligible(l) is False

    def test_no_donate_flag(self):
        l = make_view(status="Available", donate_if_unsold=False, deadline=future(10))
        assert is_donation_eligible(l) is False

    def test_non_available_not_eligible(self):
        l = make_view(status="Sold out", donate_if_unsold=True, deadline=future(10))
        assert is_donation_eligible(l) is False


# ----------------------------------------------------------- pricing logic
class TestPricingLogic:
    def test_discount_pct(self):
        assert discount_percentage(10, 20) == 50
        assert discount_percentage(15, 20) == 25
        assert discount_percentage(20, 20) == 0

    def test_no_market_price(self):
        assert discount_percentage(10, 0) == 0

    def test_savings(self):
        assert savings_amount(10, 20, 5) == 50.0


# ----------------------------------------------------------- expiry logic
class TestExpiryLogic:
    def test_past_deadline_is_expired(self):
        past = datetime.now() - timedelta(minutes=1)
        assert is_expired(past) is True

    def test_future_deadline_not_expired(self):
        fut = datetime.now() + timedelta(hours=24)
        assert is_expired(fut) is False
