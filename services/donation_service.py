"""Donation service – request, approve, decline, cancel, and collect donations.

Status machine (mirrors DemoBackend):
    Seller: Requested → Approved | Declined
            Approved  → Collected | Cancelled
    NGO:    Requested → Cancelled
            Approved  → Cancelled
"""
from __future__ import annotations

from datetime import datetime

from database.database import query_one, query_all, transaction
from logic.inventory_logic import release_stock
from models.donation import DonationRequest
from utils.demo_backend import (
    SELLER_DONATION_TRANSITIONS, NGO_DONATION_TRANSITIONS, RELEASES_STOCK, ServiceError,
)

_VIEW_SQL = """
    SELECT dr.*,
           sl.name                AS listing_name,
           sl.unit                AS unit,
           sl.location            AS location,
           sl.collection_deadline AS deadline,
           ngo_u.organisation_name  AS ngo_name,
           seller_u.organisation_name AS seller_name
    FROM   donation_requests dr
    JOIN   surplus_listings sl     ON sl.id      = dr.listing_id
    JOIN   users ngo_u             ON ngo_u.id   = dr.ngo_id
    JOIN   users seller_u          ON seller_u.id= dr.seller_id
"""


# ------------------------------------------------------------------ public API
def request_donation(listing_id: int, ngo_id: int, quantity: float, note: str = "") -> dict:
    """Create a donation request.  Reserves stock atomically."""
    row = query_one("SELECT role FROM users WHERE id = %s", (ngo_id,))
    if not row or row["role"] != "ngo":
        raise ServiceError("Only registered NGOs can request donations.")

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ServiceError("Quantity must be a number.")
    if quantity <= 0:
        raise ServiceError("Quantity must be greater than zero.")

    now = datetime.utcnow()
    with transaction() as cur:
        cur.execute(
            "SELECT * FROM surplus_listings WHERE id = %s FOR UPDATE",
            (listing_id,),
        )
        listing = cur.fetchone()
        if not listing:
            raise ServiceError("This listing no longer exists.")

        # Check donation eligibility in Python (mirrors DemoBackend)
        from models.listing import SurplusListing
        view = SurplusListing.from_row(listing).to_view_dict()
        if not view["donation_eligible"]:
            raise ServiceError("This item is not currently available for donation.")

        avail = float(listing["available_quantity"])
        if quantity > avail:
            raise ServiceError(f"Only {avail:g} {listing['unit']} is available.")

        # Reserve stock
        cur.execute(
            "UPDATE surplus_listings SET available_quantity = available_quantity - %s "
            "WHERE id = %s",
            (quantity, listing_id),
        )
        cur.execute(
            "UPDATE surplus_listings SET status = 'sold_out' "
            "WHERE id = %s AND available_quantity <= 0 AND status = 'available'",
            (listing_id,),
        )

        cur.execute(
            """
            INSERT INTO donation_requests
                (listing_id, ngo_id, seller_id, quantity, note, status, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,'Requested',%s,%s)
            """,
            (
                listing_id, ngo_id, listing["seller_id"],
                quantity, (note or "").strip(), now, now,
            ),
        )
        dr_id = cur.lastrowid

    from services.notification_service import notify
    notify(
        listing["seller_id"],
        f"NGO requested a donation of {quantity:g} {listing['unit']} for '{listing['name']}'.",
    )
    return get_donation_request(dr_id)


def ngo_requests(ngo_id: int) -> list[dict]:
    rows = query_all(_VIEW_SQL + " WHERE dr.ngo_id = %s ORDER BY dr.created_at DESC", (ngo_id,))
    return [DonationRequest.from_row(r).to_dict() for r in rows]


def seller_donation_requests(seller_id: int) -> list[dict]:
    rows = query_all(_VIEW_SQL + " WHERE dr.seller_id = %s ORDER BY dr.created_at DESC", (seller_id,))
    return [DonationRequest.from_row(r).to_dict() for r in rows]


def get_donation_request(request_id: int) -> dict | None:
    row = query_one(_VIEW_SQL + " WHERE dr.id = %s", (request_id,))
    return DonationRequest.from_row(row).to_dict() if row else None


def set_donation_status(request_id: int, actor_id: int, new_status: str) -> dict:
    """Advance or cancel a donation request."""
    dr_row = query_one("SELECT * FROM donation_requests WHERE id = %s", (request_id,))
    if not dr_row:
        raise ServiceError("Donation request not found.")

    if actor_id == dr_row["seller_id"]:
        allowed_map = SELLER_DONATION_TRANSITIONS
    elif actor_id == dr_row["ngo_id"]:
        allowed_map = NGO_DONATION_TRANSITIONS
    else:
        raise ServiceError("You are not allowed to change this.")

    current = dr_row["status"]
    if new_status not in allowed_map.get(current, []):
        raise ServiceError(f"Cannot change status from {current} to {new_status}.")

    now = datetime.utcnow()
    completed_at = now if new_status == "Collected" else None

    with transaction() as cur:
        if new_status in RELEASES_STOCK:
            release_stock(dr_row["listing_id"], float(dr_row["quantity"]), cur)
        cur.execute(
            "UPDATE donation_requests SET status=%s, updated_at=%s, completed_at=%s WHERE id=%s",
            (new_status, now, completed_at or dr_row.get("completed_at"), request_id),
        )

    from services.notification_service import notify
    listing_row = query_one("SELECT name FROM surplus_listings WHERE id=%s", (dr_row["listing_id"],))
    lname = listing_row["name"] if listing_row else "listing"
    if actor_id == dr_row["seller_id"]:
        notify(dr_row["ngo_id"], f"Your donation request for '{lname}' is now: {new_status}.")
    else:
        notify(dr_row["seller_id"], f"NGO updated their donation request for '{lname}' to: {new_status}.")

    return get_donation_request(request_id)
