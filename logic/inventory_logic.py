"""Inventory management logic for FoodBridge.

Handles atomic quantity reservation and release operations so that the
service layer can stay clean of raw SQL for stock accounting.
"""
from __future__ import annotations

from database.database import transaction
from utils.demo_backend import ServiceError


# ------------------------------------------------------------------ helpers
MASS_UNITS = ("kg", "L")


def to_kg_equivalent(quantity: float, unit: str) -> float:
    """Convert quantity to kg-equivalent for impact reporting.
    Only kg and L count; other units return 0."""
    return quantity if unit in MASS_UNITS else 0.0


def reserve_stock(listing_id: int, qty: float, cur) -> None:
    """Decrement available_quantity by *qty* with a row-level lock.
    *cur* must be an active cursor inside a transaction.
    Raises ServiceError on insufficient stock.
    """
    cur.execute(
        "SELECT available_quantity, status FROM surplus_listings "
        "WHERE id = %s FOR UPDATE",
        (listing_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ServiceError("Listing not found.")
    if row["status"] not in ("available",):
        raise ServiceError(f"This listing is {row['status']}.")
    if float(row["available_quantity"]) < qty:
        raise ServiceError(
            f"Only {float(row['available_quantity']):g} units available."
        )
    cur.execute(
        "UPDATE surplus_listings SET available_quantity = available_quantity - %s "
        "WHERE id = %s",
        (qty, listing_id),
    )
    # auto-update status to sold_out if nothing left
    cur.execute(
        "UPDATE surplus_listings SET status = 'sold_out' "
        "WHERE id = %s AND available_quantity <= 0 AND status = 'available'",
        (listing_id,),
    )


def release_stock(listing_id: int, qty: float, cur) -> None:
    """Return *qty* back to available_quantity and restore 'available' status.
    *cur* must be inside an active transaction.
    """
    cur.execute(
        "UPDATE surplus_listings "
        "SET available_quantity = available_quantity + %s, "
        "    status = CASE WHEN status = 'sold_out' THEN 'available' ELSE status END "
        "WHERE id = %s",
        (qty, listing_id),
    )
