"""Order service – place orders, change status, retrieve orders.

Status machine (mirrors DemoBackend):
    Seller: Pending → Confirmed | Rejected
            Confirmed → Ready for collection | Cancelled
            Ready for collection → Completed | Cancelled
    Buyer:  Pending → Cancelled
            Confirmed → Cancelled
"""
from __future__ import annotations

from datetime import datetime

from database.database import query_one, query_all, transaction
from logic.inventory_logic import reserve_stock, release_stock
from models.order import Order
from utils.demo_backend import (
    SELLER_ORDER_TRANSITIONS, BUYER_ORDER_TRANSITIONS, RELEASES_STOCK, ServiceError,
)

MASS_UNITS = ("kg", "L")

_VIEW_SQL = """
    SELECT o.*,
           sl.name                AS listing_name,
           sl.unit                AS unit,
           sl.location            AS location,
           sl.collection_deadline AS deadline,
           buyer.organisation_name AS buyer_name,
           seller.organisation_name AS seller_name
    FROM   orders o
    JOIN   surplus_listings sl    ON sl.id    = o.listing_id
    JOIN   users buyer            ON buyer.id = o.buyer_id
    JOIN   users seller           ON seller.id= o.seller_id
"""


# ------------------------------------------------------------------ public API
def place_order(listing_id: int, buyer_id: int, quantity: float, note: str = "") -> dict:
    """Create a purchase order.  Reserves stock atomically."""
    # Role check
    row = query_one("SELECT role FROM users WHERE id = %s", (buyer_id,))
    if not row or row["role"] != "business":
        raise ServiceError("Only business accounts can buy ingredients.")

    # Validate quantity
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ServiceError("Quantity must be a number.")
    if quantity <= 0:
        raise ServiceError("Quantity must be greater than zero.")

    now = datetime.utcnow()
    with transaction() as cur:
        # Fetch listing under lock
        cur.execute(
            "SELECT * FROM surplus_listings WHERE id = %s FOR UPDATE",
            (listing_id,),
        )
        listing = cur.fetchone()
        if not listing:
            raise ServiceError("This listing no longer exists.")

        # Business rules
        if listing["seller_id"] == buyer_id:
            raise ServiceError("You cannot buy your own listing.")

        # Compute display status
        from models.listing import SurplusListing
        view = SurplusListing.from_row(listing).computed_status()
        if view != "Available":
            raise ServiceError(f"This listing is {view.lower()}.")

        avail = float(listing["available_quantity"])
        if quantity > avail:
            raise ServiceError(f"Only {avail:g} {listing['unit']} is available.")

        # Reserve stock
        cur.execute(
            "UPDATE surplus_listings SET available_quantity = available_quantity - %s "
            "WHERE id = %s",
            (quantity, listing_id),
        )
        # Update to sold_out if exhausted
        cur.execute(
            "UPDATE surplus_listings SET status = 'sold_out' "
            "WHERE id = %s AND available_quantity <= 0 AND status = 'available'",
            (listing_id,),
        )

        unit_price = float(listing["discounted_price"])
        total = round(quantity * unit_price, 2)
        cur.execute(
            """
            INSERT INTO orders
                (listing_id, buyer_id, seller_id, quantity, unit_price, total, note, status,
                 created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'Pending',%s,%s)
            """,
            (
                listing_id, buyer_id, listing["seller_id"],
                quantity, unit_price, total,
                (note or "").strip(), now, now,
            ),
        )
        order_id = cur.lastrowid

    # Notify seller
    from services.notification_service import notify
    notify(
        listing["seller_id"],
        f"New order placed for '{listing['name']}' – {quantity:g} {listing['unit']}.",
    )

    return get_order(order_id)


def buyer_orders(buyer_id: int) -> list[dict]:
    rows = query_all(_VIEW_SQL + " WHERE o.buyer_id = %s ORDER BY o.created_at DESC", (buyer_id,))
    return [Order.from_row(r).to_dict() for r in rows]


def seller_orders(seller_id: int) -> list[dict]:
    rows = query_all(_VIEW_SQL + " WHERE o.seller_id = %s ORDER BY o.created_at DESC", (seller_id,))
    return [Order.from_row(r).to_dict() for r in rows]


def get_order(order_id: int) -> dict | None:
    row = query_one(_VIEW_SQL + " WHERE o.id = %s", (order_id,))
    return Order.from_row(row).to_dict() if row else None


def set_order_status(order_id: int, actor_id: int, new_status: str) -> dict:
    """Advance or cancel an order, releasing stock when appropriate."""
    order_row = query_one("SELECT * FROM orders WHERE id = %s", (order_id,))
    if not order_row:
        raise ServiceError("Order not found.")

    # Determine which transition map to use
    if actor_id == order_row["seller_id"]:
        allowed_map = SELLER_ORDER_TRANSITIONS
    elif actor_id == order_row["buyer_id"]:
        allowed_map = BUYER_ORDER_TRANSITIONS
    else:
        raise ServiceError("You are not allowed to change this.")

    current = order_row["status"]
    if new_status not in allowed_map.get(current, []):
        raise ServiceError(f"Cannot change status from {current} to {new_status}.")

    now = datetime.utcnow()
    completed_at = now if new_status in ("Completed",) else None

    with transaction() as cur:
        if new_status in RELEASES_STOCK:
            release_stock(order_row["listing_id"], float(order_row["quantity"]), cur)
        cur.execute(
            "UPDATE orders SET status=%s, updated_at=%s, completed_at=%s WHERE id=%s",
            (new_status, now, completed_at or order_row.get("completed_at"), order_id),
        )

    # Notifications
    from services.notification_service import notify
    listing_row = query_one("SELECT name FROM surplus_listings WHERE id=%s", (order_row["listing_id"],))
    lname = listing_row["name"] if listing_row else "listing"
    if actor_id == order_row["seller_id"]:
        notify(order_row["buyer_id"], f"Your order for '{lname}' is now: {new_status}.")
    else:
        notify(order_row["seller_id"], f"Buyer updated the order for '{lname}' to: {new_status}.")

    return get_order(order_id)


def impact_stats(user_id: int | None = None) -> dict:
    """Platform-wide or per-user impact statistics."""
    where_order = "WHERE o.status = 'Completed'"
    where_don   = "WHERE dr.status = 'Collected'"
    params_o: tuple = ()
    params_d: tuple = ()

    if user_id is not None:
        where_order += " AND (o.buyer_id = %s OR o.seller_id = %s)"
        where_don   += " AND (dr.ngo_id = %s OR dr.seller_id = %s)"
        params_o = (user_id, user_id)
        params_d = (user_id, user_id)

    order_rows = query_all(
        f"""
        SELECT o.quantity, o.total, o.completed_at, sl.unit
        FROM   orders o
        JOIN   surplus_listings sl ON sl.id = o.listing_id
        {where_order}
        """,
        params_o,
    )
    don_rows = query_all(
        f"""
        SELECT dr.quantity, dr.completed_at, sl.unit
        FROM   donation_requests dr
        JOIN   surplus_listings sl ON sl.id = dr.listing_id
        {where_don}
        """,
        params_d,
    )

    resold = donated = revenue = 0.0
    orders_completed = donations_completed = 0
    timeline: dict = {}

    for r in order_rows:
        kg = float(r["quantity"]) if r["unit"] in MASS_UNITS else 0.0
        resold += kg
        revenue += float(r["total"])
        orders_completed += 1
        if r["completed_at"]:
            d = r["completed_at"].date()
            timeline.setdefault(d, [0.0, 0.0])[0] += kg

    for r in don_rows:
        kg = float(r["quantity"]) if r["unit"] in MASS_UNITS else 0.0
        donated += kg
        donations_completed += 1
        if r["completed_at"]:
            d = r["completed_at"].date()
            timeline.setdefault(d, [0.0, 0.0])[1] += kg

    # Active listings count
    active_where = "WHERE sl.status = 'available'"
    active_params: tuple = ()
    if user_id is not None:
        active_where += " AND sl.seller_id = %s"
        active_params = (user_id,)
    active_row = query_one(
        f"SELECT COUNT(*) AS cnt FROM surplus_listings sl {active_where}", active_params
    )
    active = int(active_row["cnt"]) if active_row else 0

    return {
        "resold_kg": resold,
        "revenue": revenue,
        "orders_completed": orders_completed,
        "donated_kg": donated,
        "donations_completed": donations_completed,
        "active_listings": active,
        "timeline": [
            {"date": k, "resold_kg": v[0], "donated_kg": v[1]}
            for k, v in sorted(timeline.items())
        ],
    }
