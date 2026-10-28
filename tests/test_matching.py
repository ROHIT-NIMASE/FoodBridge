
"""Tests for FoodBridge marketplace, donation and NGO matching."""

import unittest
from datetime import datetime, timedelta

from logic.matching_logic import (
    match_listings_to_query,
    eligible_donation_listings,
    match_ngos,
)
from logic.donation_logic import is_donation_eligible
from logic.pricing_logic import discount_percentage, savings_amount
from logic.expiry_logic import is_expired


def future(hours=48):
    return datetime.now() + timedelta(hours=hours)


def make_view(**overrides):
    listing = {
        "id": 1,
        "name": "Tomatoes",
        "category": "Vegetables",
        "description": "",
        "price": 10,
        "quantity_available": 100,
        "condition": "Fresh",
        "location": "Pune",
        "deadline": future(48),
        "status": "Available",
        "donate_if_unsold": False,
        "donation_eligible": False,
        "discount_pct": 50,
        "original_price": 20,
    }
    listing.update(overrides)
    return listing


class TestMatchListingsToQuery(unittest.TestCase):

    def test_query_filters_by_name(self):
        result = match_listings_to_query(
            [make_view(name="Tomatoes"), make_view(name="Onions")],
            query="tomato",
        )
        self.assertEqual([x["name"] for x in result], ["Tomatoes"])

    def test_query_filters_by_description(self):
        result = match_listings_to_query(
            [
                make_view(description="ripe bananas"),
                make_view(description="raw onions"),
            ],
            query="banana",
        )
        self.assertEqual(len(result), 1)

    def test_location_filter(self):
        result = match_listings_to_query(
            [
                make_view(location="Kothrud, Pune"),
                make_view(location="Bandra, Mumbai"),
            ],
            location="Pune",
        )
        self.assertEqual(len(result), 1)

    def test_category_filter(self):
        result = match_listings_to_query(
            [
                make_view(category="Vegetables"),
                make_view(category="Dairy & Eggs"),
            ],
            category="Vegetables",
        )
        self.assertEqual(len(result), 1)

    def test_condition_filter(self):
        result = match_listings_to_query(
            [
                make_view(condition="Fresh"),
                make_view(condition="Good"),
            ],
            conditions=["Fresh"],
        )
        self.assertEqual(len(result), 1)

    def test_min_price_filter(self):
        result = match_listings_to_query(
            [make_view(price=5), make_view(price=20)],
            min_price=10,
        )
        self.assertTrue(all(x["price"] >= 10 for x in result))

    def test_max_price_filter(self):
        result = match_listings_to_query(
            [make_view(price=5), make_view(price=20)],
            max_price=10,
        )
        self.assertTrue(all(x["price"] <= 10 for x in result))

    def test_min_quantity_filter(self):
        result = match_listings_to_query(
            [
                make_view(quantity_available=10),
                make_view(quantity_available=200),
            ],
            min_quantity=100,
        )
        self.assertTrue(
            all(x["quantity_available"] >= 100 for x in result)
        )

    def test_non_available_excluded(self):
        result = match_listings_to_query(
            [
                make_view(status="Cancelled"),
                make_view(status="Available", name="Good"),
            ]
        )
        self.assertEqual([x["name"] for x in result], ["Good"])

    def test_sort_by_price_low_to_high(self):
        result = match_listings_to_query(
            [make_view(price=30), make_view(price=5), make_view(price=15)],
            sort="Price: low to high",
        )
        self.assertEqual(
            [x["price"] for x in result],
            sorted(x["price"] for x in result),
        )

    def test_sort_biggest_discount(self):
        result = match_listings_to_query(
            [make_view(discount_pct=10), make_view(discount_pct=80)],
            sort="Biggest discount",
        )
        self.assertGreaterEqual(
            result[0]["discount_pct"],
            result[-1]["discount_pct"],
        )

    def test_empty_results(self):
        self.assertEqual(
            match_listings_to_query([make_view()], query="xyznotfound"),
            [],
        )


class TestEligibleDonationListings(unittest.TestCase):

    def test_eligible_appear(self):
        result = eligible_donation_listings(
            [
                make_view(donation_eligible=True),
                make_view(donation_eligible=False),
            ]
        )
        self.assertEqual(len(result), 1)

    def test_sorted_by_deadline(self):
        result = eligible_donation_listings(
            [
                make_view(
                    donation_eligible=True,
                    deadline=future(30),
                    name="B",
                ),
                make_view(
                    donation_eligible=True,
                    deadline=future(5),
                    name="A",
                ),
            ]
        )
        self.assertEqual(result[0]["name"], "A")


class TestIsDonationEligible(unittest.TestCase):

    def test_eligible(self):
        listing = make_view(
            status="Available",
            donate_if_unsold=True,
            deadline=future(10),
        )
        self.assertTrue(is_donation_eligible(listing))

    def test_far_deadline_not_eligible(self):
        listing = make_view(
            status="Available",
            donate_if_unsold=True,
            deadline=future(200),
        )
        self.assertFalse(is_donation_eligible(listing))

    def test_no_donate_flag(self):
        listing = make_view(
            status="Available",
            donate_if_unsold=False,
            deadline=future(10),
        )
        self.assertFalse(is_donation_eligible(listing))

    def test_non_available_not_eligible(self):
        listing = make_view(
            status="Sold out",
            donate_if_unsold=True,
            deadline=future(10),
        )
        self.assertFalse(is_donation_eligible(listing))


class TestPricingLogic(unittest.TestCase):

    def test_discount_pct(self):
        self.assertEqual(discount_percentage(10, 20), 50)
        self.assertEqual(discount_percentage(15, 20), 25)
        self.assertEqual(discount_percentage(20, 20), 0)

    def test_no_market_price(self):
        self.assertEqual(discount_percentage(10, 0), 0)

    def test_savings(self):
        self.assertEqual(savings_amount(10, 20, 5), 50.0)


class TestExpiryLogic(unittest.TestCase):

    def test_past_deadline_is_expired(self):
        past = datetime.now() - timedelta(minutes=1)
        self.assertTrue(is_expired(past))

    def test_future_deadline_not_expired(self):
        self.assertFalse(is_expired(future(24)))


class TestMatchingLogic(unittest.TestCase):

    def setUp(self):
        self.listing = {
            "ingredient": "Potatoes",
            "quantity": 5,
            "location": "Pune",
            "food_safety_verified": True,
        }

        self.ngos = [
            {
                "name": "NGO A",
                "location": "Pune",
                "accepted_ingredients": ["Potatoes", "Tomatoes"],
                "max_quantity": 10,
            },
            {
                "name": "NGO B",
                "location": "Mumbai",
                "accepted_ingredients": ["Potatoes"],
                "max_quantity": 10,
            },
            {
                "name": "NGO C",
                "location": "Pune",
                "accepted_ingredients": ["Onions"],
                "max_quantity": 10,
            },
            {
                "name": "NGO D",
                "location": "Pune",
                "accepted_ingredients": ["Potatoes"],
                "max_quantity": 2,
            },
        ]

    def test_matches_suitable_ngo(self):
        result = match_ngos(self.listing, self.ngos)
        self.assertEqual([ngo["name"] for ngo in result], ["NGO A"])

    def test_unverified_food_not_matched(self):
        listing = {**self.listing, "food_safety_verified": False}
        self.assertEqual(match_ngos(listing, self.ngos), [])

    def test_wrong_location_not_matched(self):
        listing = {**self.listing, "location": "Delhi"}
        self.assertEqual(match_ngos(listing, self.ngos), [])

    def test_insufficient_capacity_not_matched(self):
        listing = {**self.listing, "quantity": 20}
        self.assertEqual(match_ngos(listing, self.ngos), [])

    def test_empty_ingredient_not_matched(self):
        listing = {**self.listing, "ingredient": ""}
        self.assertEqual(match_ngos(listing, self.ngos), [])

    def test_matching_is_case_insensitive(self):
        listing = {**self.listing, "ingredient": "POTATOES"}
        result = match_ngos(listing, self.ngos)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()