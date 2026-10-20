"""MySQLBackend – a drop-in replacement for DemoBackend.

Exposes the *exact* same public API that helpers.py and the UI screens use,
but delegates every call to the real MySQL-backed service layer.

To activate, change helpers.py::backend() to return MySQLBackend() instead
of DemoBackend().
"""
from __future__ import annotations

# Re-export constants so `from utils.mysql_backend import CATEGORIES, ...` works
from utils.demo_backend import (  # noqa: F401
    CATEGORIES, CONDITIONS, UNITS, MASS_UNITS,
    DONATION_WINDOW_HOURS,
    ROLE_BUSINESS, ROLE_NGO,
    SELLER_ORDER_TRANSITIONS, BUYER_ORDER_TRANSITIONS,
    SELLER_DONATION_TRANSITIONS, NGO_DONATION_TRANSITIONS,
    RELEASES_STOCK,
    ServiceError,
)

import services.user_service     as _us
import services.listing_service  as _ls
import services.order_service    as _os
import services.donation_service as _ds
import services.notification_service as _ns


class MySQLBackend:
    """Thin façade wrapping the service layer behind the DemoBackend API."""

    # ---------------------------------------------------------------- users
    def register_user(self, name, email, password, role, org_name, location, phone=""):
        # The UI's register.py passes (name, email, password, confirm, role, org_name, location)
        # but demo_backend.register_user only takes password (no confirm).
        # We call validate_registration internally, which handles confirm.
        # For compatibility, treat 'password' as both password and confirm here.
        return _us.register_user(
            name=name, email=email,
            password=password, confirm=password,   # confirm matches
            role=role, org_name=org_name, location=location, phone=phone,
        )

    def authenticate(self, email, password):
        return _us.authenticate(email, password)

    def get_user(self, user_id):
        return _us.get_user(user_id)

    # ------------------------------------------------------------- listings
    def create_listing(self, seller_id, data):
        return _ls.create_listing(seller_id, data)

    def update_listing(self, listing_id, seller_id, data):
        return _ls.update_listing(listing_id, seller_id, data)

    def cancel_listing(self, listing_id, seller_id):
        return _ls.cancel_listing(listing_id, seller_id)

    def get_listing(self, listing_id):
        return _ls.get_listing(listing_id)

    def seller_listings(self, seller_id):
        return _ls.seller_listings(seller_id)

    def search_listings(self, query="", location="", category=None, conditions=None,
                        min_price=None, max_price=None, min_quantity=None,
                        sort="Collect-by soonest"):
        return _ls.search_listings(
            query=query, location=location, category=category, conditions=conditions,
            min_price=min_price, max_price=max_price, min_quantity=min_quantity, sort=sort,
        )

    # --------------------------------------------------------------- orders
    def place_order(self, listing_id, buyer_id, quantity, note=""):
        return _os.place_order(listing_id, buyer_id, quantity, note)

    def buyer_orders(self, buyer_id):
        return _os.buyer_orders(buyer_id)

    def seller_orders(self, seller_id):
        return _os.seller_orders(seller_id)

    def set_order_status(self, order_id, actor_id, new_status):
        return _os.set_order_status(order_id, actor_id, new_status)

    # ------------------------------------------------------------ donations
    def donation_offers(self):
        return _ls.donation_offers()

    def request_donation(self, listing_id, ngo_id, quantity, note=""):
        return _ds.request_donation(listing_id, ngo_id, quantity, note)

    def ngo_requests(self, ngo_id):
        return _ds.ngo_requests(ngo_id)

    def seller_donation_requests(self, seller_id):
        return _ds.seller_donation_requests(seller_id)

    def set_donation_status(self, request_id, actor_id, new_status):
        return _ds.set_donation_status(request_id, actor_id, new_status)

    # --------------------------------------------------------------- impact
    def impact_stats(self, user_id=None):
        return _os.impact_stats(user_id)

    # --------------------------------------------------------- notifications
    def get_notifications(self, user_id, unread_only=False):
        return _ns.get_notifications(user_id, unread_only)

    def mark_all_read(self, user_id):
        return _ns.mark_all_read(user_id)

    def unread_count(self, user_id):
        return _ns.unread_count(user_id)
