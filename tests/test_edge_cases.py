
import unittest

from logic.pricing_logic import calculate_discounted_price
from logic.inventory_logic import (
    check_available_inventory,
    calculate_remaining_inventory,
)
from logic.matching_logic import match_ngos


class TestEdgeCases(unittest.TestCase):

    def test_negative_discount_rejected(self):
        with self.assertRaises(ValueError):
            calculate_discounted_price(100, -10)

    def test_discount_over_100_rejected(self):
        with self.assertRaises(ValueError):
            calculate_discounted_price(100, 101)

    def test_zero_price_rejected(self):
        with self.assertRaises(ValueError):
            calculate_discounted_price(0, 10)

    def test_zero_available_stock(self):
        self.assertTrue(check_available_inventory(0, 0)[0] is False)

    def test_exact_stock_purchase(self):
        self.assertEqual(
            calculate_remaining_inventory(5, 5),
            0,
        )

    def test_missing_listing_fields_do_not_match(self):
        self.assertEqual(match_ngos({}, []), [])

    def test_unverified_listing_does_not_match(self):
        listing = {
            "ingredient": "Potatoes",
            "quantity": 5,
            "location": "Pune",
            "food_safety_verified": False,
        }
        self.assertEqual(match_ngos(listing, []), [])


if __name__ == "__main__":
    unittest.main()
