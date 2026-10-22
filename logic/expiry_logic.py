"""Expiry / deadline logic for FoodBridge listings."""
from __future__ import annotations

from datetime import datetime


def mark_expired_listings(cur) -> int:
    """Set status='expired' on all listings whose deadline has passed and
    are still 'available' or 'sold_out'.  Returns the number of rows updated.
    """
    cur.execute(
        "UPDATE surplus_listings "
        "SET status = 'expired' "
        "WHERE status IN ('available', 'sold_out') "
        "  AND collection_deadline <= %s",
        (datetime.now(),),
    )
    return cur.rowcount


def is_expired(deadline: datetime) -> bool:
    return deadline <= datetime.now()
