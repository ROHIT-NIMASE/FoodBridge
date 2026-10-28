
import unittest

from logic.pricing_logic import (
    calculate_discounted_price,
    calculate_savings,
)


class TestPricingLogic(unittest.TestCase):

    def test_25_percent_discount(self):
        self.assertEqual(calculate_discounted_price(40, 25), 30)

    def test_full_discount(self):
        self.assertEqual(calculate_discounted_price(100, 100), 0)

    def test_zero_discount(self):
        self.assertEqual(calculate_discounted_price(100, 0), 100)

    def test_invalid_price(self):
        with self.assertRaises(ValueError):
            calculate_discounted_price(0, 25)

    def test_invalid_discount(self):
        with self.assertRaises(ValueError):
            calculate_discounted_price(100, 110)

    def test_calculate_savings(self):
        self.assertEqual(calculate_savings(40, 30), 10)

    def test_discounted_price_exceeds_original(self):
        with self.assertRaises(ValueError):
            calculate_savings(40, 50)


if __name__ == "__main__":
    unittest.main()
