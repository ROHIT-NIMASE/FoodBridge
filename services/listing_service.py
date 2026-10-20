"""Listing service – create, edit, cancel, search, and retrieve surplus listings.

All methods raise ServiceError with a user-safe message on failure.
"""
from __future__ import annotations

from datetime import datetime

from database.database import query_one, query_all, execute, transaction
from logic.validation import validate_listing, ServiceError
from logic.matching_logic import match_listings_to_query, eligible_donation_listings
from models.listing import SurplusListing

# DB status → UI condition column mapping
_CONDITION_MAP = {"Fresh": "Fresh", "Good": "Good", "Best used soon": "Best used soon"}

_VIEW_SQL = """
    SELECT sl.*,
           u.organisation_name AS seller_name,
           u.location          AS seller_location
    FROM   surplus_listings sl
    JOIN   users u ON u.id = sl.seller_id
"""


# ------------------------------------------------------------------ public API
def create_listing(seller_id: int, data: dict) -> dict:
    """Create a new surplus listing.  Returns a view dict."""
    _require_business(seller_id)
    fields = validate_listing(data)

    with transaction() as cur:
        cur.execute(
            """
            INSERT INTO surplus_listings
                (seller_id, name, category, description,
                 total_quantity, available_quantity,
                 unit, discounted_price, market_price,
                 condition_grade, location, collection_deadline, donation_enabled)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                seller_id,
                fields["name"],
                fields["category"],
                fields["description"],
                fields["quantity"],
                fields["quantity"],          # available = total on creation
                fields["unit"],
                fields["price"],
                fields["original_price"] or fields["price"],
                fields["condition"],
                fields["location"],
                fields["deadline"],
                int(fields["donate_if_unsold"]),
            ),
        )
        listing_id = cur.lastrowid

    return get_listing(listing_id)


def update_listing(listing_id: int, seller_id: int, data: dict) -> dict:
    """Edit a listing owned by seller_id.  Returns updated view dict."""
    row = _own_listing_row(listing_id, seller_id)
    if row["status"] == "cancelled":
        raise ServiceError("A cancelled listing cannot be edited.")

    fields = validate_listing(data)
    reserved = float(row["total_quantity"]) - float(row["available_quantity"])
    if fields["quantity"] < reserved:
        raise ServiceError(
            f"{reserved:g} {row['unit']} is already reserved by orders or donations, "
            f"so the total quantity cannot go below that."
        )

    new_available = fields["quantity"] - reserved
    with transaction() as cur:
        cur.execute(
            """
            UPDATE surplus_listings
            SET name=%s, category=%s, description=%s,
                total_quantity=%s, available_quantity=%s,
                unit=%s, discounted_price=%s, market_price=%s,
                condition_grade=%s, location=%s, collection_deadline=%s,
                donation_enabled=%s,
                status = CASE
                    WHEN %s <= 0 THEN 'sold_out'
                    WHEN status = 'sold_out' THEN 'available'
                    ELSE status
                END
            WHERE id=%s
            """,
            (
                fields["name"],
                fields["category"],
                fields["description"],
                fields["quantity"],
                new_available,
                fields["unit"],
                fields["price"],
                fields["original_price"] or fields["price"],
                fields["condition"],
                fields["location"],
                fields["deadline"],
                int(fields["donate_if_unsold"]),
                new_available,   # for the CASE expression
                listing_id,
            ),
        )
    return get_listing(listing_id)


def cancel_listing(listing_id: int, seller_id: int) -> dict:
    """Cancel a listing and cascade-cancel all open orders/donation requests."""
    row = _own_listing_row(listing_id, seller_id)
    if row["status"] == "cancelled":
        raise ServiceError("This listing is already cancelled.")

    from services.notification_service import notify  # avoid circular import

    with transaction() as cur:
        cur.execute(
            "UPDATE surplus_listings SET status='cancelled', available_quantity=0 WHERE id=%s",
            (listing_id,),
        )
        # Cancel open orders
        cur.execute(
            "SELECT id, buyer_id, quantity FROM orders "
            "WHERE listing_id=%s AND status IN ('Pending','Confirmed','Ready for collection')",
            (listing_id,),
        )
        open_orders = cur.fetchall()
        for o in open_orders:
            cur.execute(
                "UPDATE orders SET status='Cancelled', updated_at=%s WHERE id=%s",
                (datetime.utcnow(), o["id"]),
            )

        # Cancel open donation requests
        cur.execute(
            "SELECT id, ngo_id, quantity FROM donation_requests "
            "WHERE listing_id=%s AND status IN ('Requested','Approved')",
            (listing_id,),
        )
        open_dr = cur.fetchall()
        for d in open_dr:
            cur.execute(
                "UPDATE donation_requests SET status='Cancelled', updated_at=%s WHERE id=%s",
                (datetime.utcnow(), d["id"]),
            )

    # Send notifications outside the transaction (best-effort)
    listing_name = row["name"]
    for o in open_orders:
        notify(o["buyer_id"], f"Your order for '{listing_name}' was cancelled because the listing was removed.")
    for d in open_dr:
        notify(d["ngo_id"], f"Your donation request for '{listing_name}' was cancelled because the listing was removed.")

    return get_listing(listing_id)


def get_listing(listing_id: int) -> dict | None:
    row = query_one(_VIEW_SQL + " WHERE sl.id = %s", (listing_id,))
    return SurplusListing.from_row(row).to_view_dict() if row else None


def seller_listings(seller_id: int) -> list[dict]:
    rows = query_all(_VIEW_SQL + " WHERE sl.seller_id = %s ORDER BY sl.created_at DESC", (seller_id,))
    return [SurplusListing.from_row(r).to_view_dict() for r in rows]


def search_listings(
    query: str = "",
    location: str = "",
    category=None,
    conditions=None,
    min_price=None,
    max_price=None,
    min_quantity=None,
    sort: str = "Collect-by soonest",
) -> list[dict]:
    """Public marketplace: only listings that can still be bought."""
    # Fetch all non-cancelled rows from DB; status computation (Expired, Sold out) is in the model
    rows = query_all(
        _VIEW_SQL + " WHERE sl.status NOT IN ('cancelled') ORDER BY sl.collection_deadline",
    )
    all_views = [SurplusListing.from_row(r).to_view_dict() for r in rows]
    return match_listings_to_query(
        all_views, query=query, location=location, category=category,
        conditions=conditions, min_price=min_price, max_price=max_price,
        min_quantity=min_quantity, sort=sort,
    )


def donation_offers() -> list[dict]:
    """Listings an NGO may request: opted-in, available, and near deadline."""
    rows = query_all(
        _VIEW_SQL + " WHERE sl.status NOT IN ('cancelled') AND sl.donation_enabled = 1",
    )
    all_views = [SurplusListing.from_row(r).to_view_dict() for r in rows]
    return eligible_donation_listings(all_views)


# ------------------------------------------------------------------ internals
def _require_business(user_id: int):
    from database.database import query_one as qo
    row = qo("SELECT role FROM users WHERE id = %s", (user_id,))
    if not row or row["role"] != "business":
        raise ServiceError("Only business accounts can list ingredients.")


def _own_listing_row(listing_id: int, seller_id: int) -> dict:
    row = query_one("SELECT * FROM surplus_listings WHERE id = %s", (listing_id,))
    if not row:
        raise ServiceError("Listing not found.")
    if row["seller_id"] != seller_id:
        raise ServiceError("You can only manage your own listings.")
    return row
