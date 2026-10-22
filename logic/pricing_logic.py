"""Pricing / discount calculation logic for FoodBridge."""
from __future__ import annotations


def discount_percentage(discounted_price: float, market_price: float) -> int:
    """Return the integer percentage discount, e.g. 40 for 40% off."""
    if not market_price or market_price <= 0:
        return 0
    return round((1 - discounted_price / market_price) * 100)


def savings_amount(discounted_price: float, market_price: float, quantity: float) -> float:
    """Total money saved vs market price for a given quantity."""
    return round((market_price - discounted_price) * quantity, 2)
