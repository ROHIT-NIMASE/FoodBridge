
"""Donation eligibility logic for FoodBridge."""

from datetime import datetime, timedelta

DONATION_WINDOW_HOURS = 48


def is_donation_eligible(listing: dict) -> bool:
    """Check whether a listing is eligible to be considered for donation."""

    if listing.get("status") != "Available":
        return False

    if not listing.get("donate_if_unsold"):
        return False

    deadline = listing.get("deadline") or listing.get("collection_deadline")

    if deadline is None:
        return False

    now = datetime.now()

    if deadline <= now:
        return False

    return deadline <= now + timedelta(hours=DONATION_WINDOW_HOURS)


def check_donation_eligibility(
    available_quantity,
    condition,
    deadline,
    now,
    food_safety_verified,
):
    """Validate quantity, condition, deadline and food-safety verification."""

    if available_quantity <= 0:
        return False, "No surplus quantity available."

    if not isinstance(condition, str) or condition.strip().lower() not in {
        "fresh",
        "good",
    }:
        return False, "Ingredient condition is unsuitable for donation."

    if deadline <= now:
        return False, "The donation deadline has passed."

    if not food_safety_verified:
        return False, "Food safety has not been verified."

    return True, "Ingredient is eligible for donation."


def update_donation_status(current_status, new_status):
    """Validate donation status transitions."""

    allowed_transitions = {
        "pending": {"accepted", "rejected"},
        "accepted": {"collected", "cancelled"},
        "rejected": set(),
        "collected": set(),
        "cancelled": set(),
    }

    if current_status not in allowed_transitions:
        raise ValueError("Invalid current donation status.")

    if new_status not in allowed_transitions[current_status]:
        raise ValueError("Invalid donation status transition.")

    return new_status
