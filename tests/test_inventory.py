
import unittest

from logic.inventory_logic import (
    check_available_inventory,
    calculate_remaining_inventory,
)


class TestInventoryLogic(unittest.TestCase):

    def test_sufficient_stock(self):
        self.assertTrue(check_available_inventory(10, 5)[0])

    def test_insufficient_stock(self):
        self.assertFalse(check_available_inventory(3, 5)[0])

    def test_zero_quantity_rejected(self):
        self.assertFalse(check_available_inventory(10, 0)[0])

    def test_negative_quantity_rejected(self):
        self.assertFalse(check_available_inventory(10, -2)[0])

    def test_remaining_inventory(self):
        self.assertEqual(calculate_remaining_inventory(10, 4), 6)

    def test_all_stock_purchased(self):
        self.assertEqual(calculate_remaining_inventory(10, 10), 0)

    def test_negative_available_stock_rejected(self):
        self.assertFalse(check_available_inventory(-1, 1)[0])

    def test_overselling_raises_error(self):
        with self.assertRaises(ValueError):
            calculate_remaining_inventory(3, 5)


if __name__ == "__main__":
    unittest.main()
