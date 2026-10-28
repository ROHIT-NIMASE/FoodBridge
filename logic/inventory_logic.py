
"""Inventory management logic for FoodBridge."""

from __future__ import annotations

from database.database import transaction
from utils.demo_backend import ServiceError


MASS_UNITS = ("kg", "L")


def to_kg_equivalent(quantity: float, unit: str) -> float:
    """Convert supported mass/volume quantities for impact reporting."""
    return quantity if unit in MASS_UNITS else 0.0


def reserve_stock(listing_id: int, qty: float, cur) -> None:
    """Reserve stock atomically inside an active database transaction."""

    if qty <= 0:
        raise ValueError("Requested quantity must be positive.")

    cur.execute(
        "SELECT available_quantity, status FROM surplus_listings "
        "WHERE id = %s FOR UPDATE",
        (listing_id,),
    )
    row = cur.fetchone()

    if not row:
        raise ServiceError("Listing not found.")

    if row["status"] != "available":
        raise ServiceError(f"This listing is {row['status']}.")

    available = float(row["available_quantity"])

    if available < qty:
        raise ServiceError(f"Only {available:g} units available.")

    cur.execute(
        "UPDATE surplus_listings "
        "SET available_quantity = available_quantity - %s "
        "WHERE id = %s",
        (qty, listing_id),
    )

    cur.execute(
        "UPDATE surplus_listings SET status = 'sold_out' "
        "WHERE id = %s AND available_quantity <= 0 "
        "AND status = 'available'",
        (listing_id,),
    )


def release_stock(listing_id: int, qty: float, cur) -> None:
    """Release previously reserved stock inside an active transaction."""

    if qty <= 0:
        raise ValueError("Released quantity must be positive.")

    cur.execute(
        "UPDATE surplus_listings "
        "SET available_quantity = available_quantity + %s, "
        "status = CASE WHEN status = 'sold_out' "
        "THEN 'available' ELSE status END "
        "WHERE id = %s",
        (qty, listing_id),
    )

    if cur.rowcount == 0:
        raise ServiceError("Listing not found.")


def check_available_inventory(available_quantity, requested_quantity):
    """Validate stock quantities without accessing the database."""

    if available_quantity < 0:
        return False, "Available quantity cannot be negative."

    if requested_quantity <= 0:
        return False, "Requested quantity must be positive."

    if requested_quantity > available_quantity:
        return False, "Insufficient stock available."

    return True, "Sufficient stock available."


def calculate_remaining_inventory(available_quantity, requested_quantity):
    """Calculate remaining stock after validating a purchase quantity."""

    is_valid, message = check_available_inventory(
        available_quantity,
        requested_quantity,
    )

    if not is_valid:
        raise ValueError(message)

    return available_quantity - requested_quantity
