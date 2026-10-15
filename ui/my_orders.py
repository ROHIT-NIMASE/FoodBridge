"""Order history for buyers, plus the shared order row used by the seller dashboard."""
import streamlit as st

from utils import helpers as h

STATUS_FILTERS = ["All", "Pending", "Confirmed", "Ready for collection", "Completed", "Cancelled", "Rejected"]


def order_row(order, perspective: str):
    """Render one order. perspective is 'buyer' or 'seller' and decides which actions are offered."""
    user = h.current_user()
    transitions = h.BUYER_ORDER_TRANSITIONS if perspective == "buyer" else h.SELLER_ORDER_TRANSITIONS
    other = order["seller_name"] if perspective == "buyer" else order["buyer_name"]
    with st.container(border=True):
        top, total = st.columns([3, 1])
        top.markdown(f'<span class="fb-title">{h.esc(order["listing_name"])}</span> '
                     f'× {h.qty(order["quantity"], order["unit"])} {h.badge(order["status"])}',
                     unsafe_allow_html=True)
        total.markdown(f'**{h.money(order["total"])}**')
        st.markdown(h.status_steps(order["status"], h.ORDER_STEPS), unsafe_allow_html=True)
        st.markdown(
            f'<div class="fb-meta">{"🏪 Seller" if perspective == "buyer" else "🧾 Buyer"}: {h.esc(other)} · '
            f'📍 {h.esc(order["location"])} · ⏰ Collect by {h.fmt_dt(order["deadline"])}</div>'
            f'<div class="fb-meta">Order #{order["id"]} · placed {h.fmt_dt(order["created_at"])}'
            f'{" · updated " + h.fmt_dt(order["updated_at"]) if order["updated_at"] != order["created_at"] else ""}</div>',
            unsafe_allow_html=True)
        if order["note"]:
            st.caption(f"Note: {order['note']}")
        actions = transitions.get(order["status"], [])
        if actions:
            cols = st.columns(max(len(actions), 1) + 1)
            for col, new_status in zip(cols, actions):
                negative = new_status in ("Cancelled", "Rejected")
                with col:
                    h.confirm_button(
                        {"Cancelled": "Cancel order", "Rejected": "Reject"}.get(new_status, f"Mark {new_status.lower()}"),
                        f"{'Cancel' if new_status == 'Cancelled' else new_status} order #{order['id']} "
                        f"({order['listing_name']})?" if negative else
                        f"Move order #{order['id']} to “{new_status}”?",
                        lambda s=new_status: h.backend().set_order_status(order["id"], user["id"], s),
                        f"Order #{order['id']} is now {new_status.lower()}.",
                        key=f"{perspective}_order_{order['id']}_{new_status}",
                        type="secondary" if negative else "primary", confirm_label="Yes, confirm",
                        use_container_width=True)


def render():
    user = h.current_user()
    st.title("My orders")
    h.show_flashes()
    orders = h.backend().buyer_orders(user["id"])
    if not orders:
        st.info("You haven't placed any orders yet.")
        if st.button("Browse the marketplace", type="primary"):
            h.go("marketplace")
        return
    c1, c2 = st.columns([2, 1])
    search = c1.text_input("Search orders", placeholder="Ingredient or seller")
    status = c2.selectbox("Status", STATUS_FILTERS)
    shown = [o for o in orders
             if (status == "All" or o["status"] == status)
             and search.lower() in (o["listing_name"] + " " + o["seller_name"]).lower()]
    st.caption(f"Showing {len(shown)} of {len(orders)} orders")
    for o in shown:
        order_row(o, "buyer")
    if not shown:
        st.info("No orders match these filters.")
