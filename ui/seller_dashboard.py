"""Seller dashboard: manage listings, incoming orders and NGO donation requests."""
import streamlit as st

from ui.my_orders import order_row
from ui.donation_requests import request_row
from utils import helpers as h


def render():
    user = h.current_user()
    be = h.backend()
    st.title("Seller dashboard")
    h.show_flashes()

    listings = be.seller_listings(user["id"])
    orders = be.seller_orders(user["id"])
    donations = be.seller_donation_requests(user["id"])
    live = [l for l in listings if l["status"] == "Available"]
    pending = [o for o in orders if o["status"] == "Pending"]
    open_donations = [d for d in donations if d["status"] == "Requested"]
    h.metric_row([("Active listings", len(live)),
                  ("Pending orders", len(pending)),
                  ("NGO requests", len(open_donations)),
                  ("Revenue", h.money(sum(o["total"] for o in orders if o["status"] == "Completed")))])

    if st.button("➕ Add surplus ingredient", type="primary"):
        h.go("listing_form", editing_listing=None)

    t_list, t_orders, t_don = st.tabs([f"My listings ({len(listings)})",
                                       f"Incoming orders ({len(orders)})",
                                       f"NGO requests ({len(donations)})"])
    with t_list:
        if not listings:
            st.info("You haven't listed anything yet. Add your first surplus ingredient.")
        for l in listings:
            _listing_row(l, user)
    with t_orders:
        if not orders:
            st.info("Orders from buyers will appear here.")
        for o in orders:
            order_row(o, "seller")
    with t_don:
        if not donations:
            st.info("Requests from NGOs for your donation-eligible items will appear here.")
        for d in donations:
            request_row(d, "seller")


def _listing_row(l, user):
    left, tone = h.time_left(l["deadline"])
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 2])
        c1.markdown(f'<span class="fb-title">{h.esc(l["name"])}</span> {h.badge(l["status"])}<br>'
                    f'<span class="fb-meta">{h.badge(l["condition"])} 📍 {h.esc(l["location"])}</span>',
                    unsafe_allow_html=True)
        c2.markdown(f'<div class="fb-meta">📦 <b>{h.qty(l["quantity_available"], l["unit"])}</b> available '
                    f'/ {h.qty(l["quantity"], l["unit"])}</div>'
                    f'<div class="fb-meta">🔒 {h.qty(l["reserved"], l["unit"])} reserved</div>',
                    unsafe_allow_html=True)
        c3.markdown(f'<div class="fb-meta">{h.money(l["price"])}/{h.esc(l["unit"])}</div>'
                    f'<div class="fb-meta">⏰ {h.fmt_dt(l["deadline"])} {h.badge(left, tone) if l["status"] == "Available" else ""}</div>',
                    unsafe_allow_html=True)
        if l["status"] != "Cancelled":
            b1, b2, _ = st.columns([1, 1, 2])
            if b1.button("Edit", key=f"edit_{l['id']}", use_container_width=True):
                h.go("listing_form", editing_listing=l["id"])
            with b2:
                h.confirm_button("Cancel listing",
                                 f"Cancel “{l['name']}”? Open orders and donation requests for it will be cancelled too.",
                                 lambda: h.backend().cancel_listing(l["id"], user["id"]),
                                 f"“{l['name']}” was cancelled.", key=f"cancel_{l['id']}",
                                 confirm_label="Yes, cancel listing", use_container_width=True)
