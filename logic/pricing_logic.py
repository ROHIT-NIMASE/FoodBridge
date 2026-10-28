
"""Pricing and discount calculation logic for FoodBridge."""


def discount_percentage(discounted_price: float, market_price: float) -> int:
    """Return the integer percentage discount."""

    if not market_price or market_price <= 0:
        return 0

    return round((1 - discounted_price / market_price) * 100)


def savings_amount(
    discounted_price: float,
    market_price: float,
    quantity: float,
) -> float:
    """Calculate total savings for the given quantity."""

    return round((market_price - discounted_price) * quantity, 2)


def calculate_discounted_price(original_price, discount_percent):
    """Calculate the price after applying a percentage discount."""

    if original_price <= 0:
        raise ValueError("Original price must be greater than zero.")

    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100.")

    return round(original_price * (1 - discount_percent / 100), 2)


def calculate_savings(original_price, discounted_price):
    """Calculate per-unit savings."""

    if original_price < 0 or discounted_price < 0:
        raise ValueError("Prices cannot be negative.")

    if discounted_price > original_price:
        raise ValueError("Discounted price cannot exceed original price.")

    return round(original_price - discounted_price, 2)
