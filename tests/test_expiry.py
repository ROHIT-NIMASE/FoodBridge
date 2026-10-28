
import unittest
from datetime import datetime, timedelta

from logic.expiry_logic import is_listing_expired, can_purchase


class TestExpiryLogic(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now()
        self.future = self.now + timedelta(hours=2)
        self.past = self.now - timedelta(hours=2)

    def test_future_deadline_not_expired(self):
        self.assertFalse(is_listing_expired(self.future, self.now))

    def test_past_deadline_expired(self):
        self.assertTrue(is_listing_expired(self.past, self.now))

    def test_deadline_equal_to_now_is_expired(self):
        self.assertTrue(is_listing_expired(self.now, self.now))

    def test_purchase_with_valid_deadline(self):
        result, message = can_purchase(
            self.future, 10, 5, self.now
        )
        self.assertTrue(result)

    def test_purchase_after_deadline_rejected(self):
        result, message = can_purchase(
            self.past, 10, 5, self.now
        )
        self.assertFalse(result)

    def test_purchase_with_insufficient_stock_rejected(self):
        result, message = can_purchase(
            self.future, 2, 5, self.now
        )
        self.assertFalse(result)

    def test_zero_purchase_quantity_rejected(self):
        result, message = can_purchase(
            self.future, 10, 0, self.now
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
