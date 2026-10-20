"""Donation eligibility logic for FoodBridge."""
from __future__ import annotations

from datetime import datetime, timedelta

DONATION_WINDOW_HOURS = 48


def is_donation_eligible(listing: dict) -> bool:
    """Return True if a listing dict is currently eligible for donation.

    Criteria:
    - status == 'Available'
    - donation_enabled (donate_if_unsold) is True
    - collection deadline is within the next DONATION_WINDOW_HOURS hours
    """
    if listing.get("status") != "Available":
        return False
    if not listing.get("donate_if_unsold"):
        return False
    deadline = listing.get("deadline") or listing.get("collection_deadline")
    if deadline is None:
        return False
    return deadline <= datetime.now() + timedelta(hours=DONATION_WINDOW_HOURS)
