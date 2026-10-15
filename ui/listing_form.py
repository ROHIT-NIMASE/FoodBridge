"""Add / edit a surplus listing."""
from datetime import datetime, time, timedelta

import streamlit as st

from utils import helpers as h


def _leave():
    st.session_state.pop("editing_listing", None)
    h.go("seller_dashboard")


def render():
    user = h.current_user()
    editing_id = st.session_state.get("editing_listing")
    existing = h.backend().get_listing(editing_id) if editing_id else None
    if editing_id and (not existing or existing["seller_id"] != user["id"]):
        st.error("That listing could not be found.")
        if st.button("Back to seller dashboard"):
            _leave()
        return
    if existing and existing["status"] == "Cancelled":
        st.warning("Cancelled listings cannot be edited.")
        if st.button("Back to seller dashboard"):
            _leave()
        return

    st.title("Edit listing" if existing else "Add surplus ingredient")
    if existing and existing["reserved"]:
        st.info(f"{h.qty(existing['reserved'], existing['unit'])} is already reserved by orders or donation requests, "
                "so total quantity cannot go below that.")
    e = existing or {}
    default_deadline = e.get("deadline") or datetime.now() + timedelta(days=2)

    with st.form("listing_form"):
        name = st.text_input("Ingredient name", value=e.get("name", ""), placeholder="e.g. Tomatoes")
        c1, c2 = st.columns(2)
        category = c1.selectbox("Category", h.CATEGORIES, index=h.CATEGORIES.index(e.get("category", "Vegetables")))
        condition = c2.selectbox("Freshness / condition", h.CONDITIONS,
                                 index=h.CONDITIONS.index(e.get("condition", "Fresh")))
        c3, c4 = st.columns(2)
        quantity = c3.number_input("Total quantity", min_value=0.0, value=float(e.get("quantity", 0.0)), step=1.0)
        unit = c4.selectbox("Unit", h.UNITS, index=h.UNITS.index(e.get("unit", "kg")))
        c5, c6 = st.columns(2)
        price = c5.number_input("Price per unit (₹)", min_value=0.0, value=float(e.get("price", 0.0)), step=1.0)
        original = c6.number_input("Normal market price per unit (₹)", min_value=0.0,
                                   value=float(e.get("original_price") or 0.0), step=1.0,
                                   help="Optional. Used to show the discount to buyers.")
        location = st.text_input("Collection location", value=e.get("location", user["location"]))
        c7, c8 = st.columns(2)
        deadline_date = c7.date_input("Collection deadline (date)", value=default_deadline.date())
        deadline_time = c8.time_input("Collection deadline (time)", value=default_deadline.time().replace(second=0, microsecond=0))
        description = st.text_area("Description (optional)", value=e.get("description", ""),
                                   placeholder="Storage, packaging, minimum pickup…")
        donate = st.checkbox("If unsold close to the deadline, offer to registered NGOs",
                             value=e.get("donate_if_unsold", False))
        save, cancel = st.columns(2)
        submitted = save.form_submit_button("Save changes" if existing else "Publish listing", type="primary",
                                            use_container_width=True)
        cancelled = cancel.form_submit_button("Cancel", use_container_width=True)

    if cancelled:
        _leave()
    if submitted:
        deadline = datetime.combine(deadline_date, deadline_time)
        errors = h.required_errors(**{"Ingredient name": name, "Collection location": location})
        if quantity <= 0: errors.append("Quantity must be greater than zero.")
        if price <= 0: errors.append("Price per unit must be greater than zero.")
        if original and price and original < price:
            errors.append("Market price cannot be lower than your discounted price.")
        if deadline <= datetime.now(): errors.append("Collection deadline must be in the future.")
        if errors:
            h.show_errors(errors)
            return
        data = dict(name=name, category=category, condition=condition, quantity=quantity, unit=unit, price=price,
                    original_price=original or None, location=location, deadline=deadline,
                    description=description, donate_if_unsold=donate)
        try:
            if existing:
                h.backend().update_listing(existing["id"], user["id"], data)
                h.flash(f"“{name}” was updated.")
            else:
                h.backend().create_listing(user["id"], data)
                h.flash(f"“{name}” is now live on the marketplace.")
        except ValueError as err:
            st.error(str(err), icon="⚠️")
            return
        _leave()
