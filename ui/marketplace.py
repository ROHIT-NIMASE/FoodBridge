"""Marketplace: browse, search and filter surplus ingredients; ingredient details and purchase request."""
import math

import streamlit as st

from utils import helpers as h

SORTS = ["Collect-by soonest", "Price: low to high", "Price: high to low", "Quantity: most first", "Biggest discount"]


def card_html(l) -> str:
    left, tone = h.time_left(l["deadline"])
    price = f'{h.money(l["price"])}<small>/{h.esc(l["unit"])}</small>'
    if l["discount_pct"] > 0:
        price += f'<s>{h.money(l["original_price"])}</s><span class="fb-off">{l["discount_pct"]}% off</span>'
    return "".join([
        f'<div class="fb-head"><span class="fb-title">{h.esc(l["name"])}</span>{h.badge(l["condition"])}</div>',
        f'<div class="fb-price">{price}</div>',
        f'<div class="fb-meta">📦 {h.qty(l["quantity_available"], l["unit"])} available</div>',
        f'<div class="fb-meta">📍 {h.esc(l["location"])}</div>',
        f'<div class="fb-meta">⏰ Collect by {h.fmt_dt(l["deadline"])} {h.badge(left, tone)}</div>',
        f'<div class="fb-meta">🏪 {h.esc(l["seller_name"])}</div>'])


def render():
    if st.session_state.get("selected_listing"):
        return _detail(st.session_state["selected_listing"])
    user = h.current_user()
    st.title("Marketplace")
    st.caption("Surplus raw ingredients from nearby businesses, at discounted prices.")
    h.show_flashes()

    everything = h.backend().search_listings()
    top_price = max([math.ceil(l["price"]) for l in everything], default=100)

    query = st.text_input("Search ingredients", placeholder="Try tomatoes, paneer, flour…", key="mk_query")
    with st.expander("Filters", expanded=False):
        c1, c2, c3 = st.columns(3)
        location = c1.text_input("Location / area", placeholder="e.g. Kothrud", key="mk_loc")
        category = c2.selectbox("Category", ["All"] + h.CATEGORIES, key="mk_cat")
        sort = c3.selectbox("Sort by", SORTS, key="mk_sort")
        c4, c5, c6 = st.columns(3)
        price_range = c4.slider("Price per unit (₹)", 0, top_price, (0, top_price), key="mk_price")
        min_qty = c5.number_input("Minimum quantity available", min_value=0.0, value=0.0, step=5.0, key="mk_qty")
        conditions = c6.multiselect("Condition", h.CONDITIONS, key="mk_cond")

    results = h.backend().search_listings(
        query=query, location=location, category=category, conditions=conditions,
        min_price=price_range[0], max_price=price_range[1], min_quantity=min_qty or None, sort=sort)

    st.markdown(f"**{len(results)}** ingredient{'s' if len(results) != 1 else ''} found")
    if not results:
        st.info("No ingredients match these filters. Try clearing the search or widening the price range.")
        return
    for row_start in range(0, len(results), 3):
        cols = st.columns(3)
        for col, l in zip(cols, results[row_start:row_start + 3]):
            with col, st.container(border=True):
                st.markdown(card_html(l), unsafe_allow_html=True)
                mine = l["seller_id"] == user["id"]
                if st.button("Your listing · view" if mine else "View details", key=f"view_{l['id']}",
                             use_container_width=True):
                    st.session_state["selected_listing"] = l["id"]
                    st.rerun()


def _back():
    st.session_state.pop("selected_listing", None)
    st.rerun()


def _detail(listing_id):
    user = h.current_user()
    l = h.backend().get_listing(listing_id)
    if st.button("← Back to marketplace"):
        _back()
    if not l:
        st.error("This listing no longer exists.")
        return
    h.show_flashes()
    left, tone = h.time_left(l["deadline"])
    st.title(l["name"])
    st.markdown(f'{h.badge(l["status"])} {h.badge(l["condition"])} {h.badge(l["category"], "muted")}',
                unsafe_allow_html=True)

    info, buy = st.columns([3, 2])
    with info:
        with st.container(border=True):
            st.markdown("".join([
                f'<div class="fb-price">{h.money(l["price"])}<small>/{h.esc(l["unit"])}</small>'
                + (f'<s>{h.money(l["original_price"])}</s><span class="fb-off">{l["discount_pct"]}% off</span>'
                   if l["discount_pct"] > 0 else "") + "</div>",
                f'<div class="fb-meta">📦 <b>{h.qty(l["quantity_available"], l["unit"])}</b> available '
                f'of {h.qty(l["quantity"], l["unit"])} listed</div>',
                f'<div class="fb-meta">📍 {h.esc(l["location"])}</div>',
                f'<div class="fb-meta">⏰ Collection deadline: <b>{h.fmt_dt(l["deadline"])}</b> {h.badge(left, tone)}</div>',
                f'<div class="fb-meta">🏪 Sold by {h.esc(l["seller_name"])}</div>']), unsafe_allow_html=True)
            if l["description"]:
                st.write(l["description"])
        if l["donation_eligible"]:
            st.info("If this is not sold, the seller may offer it to a registered NGO.", icon="🤝")

    with buy:
        with st.container(border=True):
            st.subheader("Request to buy")
            if l["seller_id"] == user["id"]:
                st.info("This is your own listing.")
                if st.button("Edit listing", use_container_width=True):
                    h.go("listing_form", editing_listing=l["id"], selected_listing=None)
            elif user["role"] != h.ROLE_BUSINESS:
                st.info("NGOs receive surplus through donation offers instead of purchases.")
            elif l["status"] != "Available":
                st.warning(f"This listing is {l['status'].lower()} and can no longer be ordered.")
            else:
                amount = st.number_input(f"Quantity ({l['unit']})", min_value=0.0, max_value=float(l["quantity_available"]),
                                         value=min(1.0, float(l["quantity_available"])), step=1.0, key=f"buy_qty_{l['id']}")
                note = st.text_area("Note to seller (optional)", key=f"buy_note_{l['id']}", height=80,
                                    placeholder="Preferred pickup time, packaging…")
                total = amount * l["price"]
                st.markdown(f"**Total: {h.money(total)}**")
                if amount <= 0:
                    st.caption("Enter a quantity greater than zero to continue.")

                def place():
                    h.backend().place_order(l["id"], user["id"], amount, note)
                    st.session_state.pop("selected_listing", None)
                    st.session_state["page"] = "my_orders"

                h.confirm_button("Submit purchase request",
                                 f"Request {h.qty(amount, l['unit'])} of {l['name']} for {h.money(total)}? "
                                 "The seller will confirm before it becomes final.",
                                 place, "Purchase request sent. Track it under My orders.",
                                 key=f"buy_{l['id']}", confirm_label="Send request", type="primary",
                                 disabled=amount <= 0, use_container_width=True)
