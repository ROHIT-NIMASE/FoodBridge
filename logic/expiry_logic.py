
"""Expiry and deadline logic for FoodBridge listings."""

from datetime import datetime


def mark_expired_listings(cur) -> int:
    """Mark listings as expired when their collection deadline passes."""

    cur.execute(
        "UPDATE surplus_listings "
        "SET status = 'expired' "
        "WHERE status IN ('available', 'sold_out') "
        "AND collection_deadline <= %s",
        (datetime.now(),),
    )

    return cur.rowcount


def is_expired(deadline: datetime) -> bool:
    """Return True when a deadline has passed."""
    return deadline <= datetime.now()


def is_listing_expired(deadline, now=None):
    """Check whether a listing has expired using an optional test time."""
    now = now or datetime.now()
    return now >= deadline


def can_purchase(
    deadline,
    available_quantity,
    requested_quantity,
    now=None,
):
    """Validate the deadline and stock before a purchase."""

    if is_listing_expired(deadline, now):
        return False, "This listing has expired."

    if requested_quantity <= 0:
        return False, "Requested quantity must be positive."

    if available_quantity < requested_quantity:
        return False, "Insufficient stock available."

    return True, "Purchase can proceed."
