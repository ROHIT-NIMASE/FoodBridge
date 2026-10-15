"""Buyer dashboard: order overview and what's ending soon."""
import streamlit as st

from ui.marketplace import card_html
from ui.my_orders import order_row
from utils import helpers as h


def render():
    user = h.current_user()
    st.title("Buyer dashboard")
    h.show_flashes()
    orders = h.backend().buyer_orders(user["id"])
    active = [o for o in orders if o["status"] in ("Pending", "Confirmed", "Ready for collection")]
    h.metric_row([("Active orders", len(active)),
                  ("Awaiting seller", sum(o["status"] == "Pending" for o in orders)),
                  ("Ready to collect", sum(o["status"] == "Ready for collection" for o in orders)),
                  ("Total spent", h.money(sum(o["total"] for o in orders if o["status"] == "Completed")))])

    st.subheader("Active orders")
    if not active:
        st.info("No active orders. Browse the marketplace to find surplus ingredients.")
    for o in active[:5]:
        order_row(o, "buyer")
    if len(active) > 5 or orders:
        if st.button("View full order history"):
            h.go("my_orders")

    st.subheader("Ending soon on the marketplace")
    soon = [l for l in h.backend().search_listings(sort="Collect-by soonest")
            if l["seller_id"] != user["id"]][:3]
    cols = st.columns(3)
    for col, l in zip(cols, soon):
        with col, st.container(border=True):
            st.markdown(card_html(l), unsafe_allow_html=True)
            if st.button("View details", key=f"soon_{l['id']}", use_container_width=True):
                h.go("marketplace", selected_listing=l["id"])
