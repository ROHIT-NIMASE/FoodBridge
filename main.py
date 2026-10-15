"""FoodBridge – entry point.  Run with:  streamlit run main.py"""
import streamlit as st

from ui import (buyer_dashboard, donation_requests, impact_dashboard, listing_form, login, marketplace,
                my_orders, ngo_dashboard, register, seller_dashboard)
from utils import helpers as h

PAGES = {
    "login": login.render, "register": register.render,
    "marketplace": marketplace.render, "listing_form": listing_form.render,
    "seller_dashboard": seller_dashboard.render, "buyer_dashboard": buyer_dashboard.render,
    "my_orders": my_orders.render, "ngo_dashboard": ngo_dashboard.render,
    "donation_requests": donation_requests.render, "impact_dashboard": impact_dashboard.render,
}
NAV = {
    h.ROLE_BUSINESS: [("marketplace", "🛒 Marketplace"), ("seller_dashboard", "📦 Seller dashboard"),
                      ("buyer_dashboard", "🧾 Buyer dashboard"), ("my_orders", "📋 My orders"),
                      ("impact_dashboard", "🌱 Impact")],
    h.ROLE_NGO: [("ngo_dashboard", "🤝 Donation offers"), ("donation_requests", "📨 My requests"),
                 ("impact_dashboard", "🌱 Impact")],
}


def sidebar(user, page):
    with st.sidebar:
        st.markdown('<div class="fb-brand">🌿 FoodBridge</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="fb-sub">{h.esc(user["org_name"])}<br>'
                    f'{"NGO" if user["role"] == h.ROLE_NGO else "Business"} · {h.esc(user["location"])}</div>',
                    unsafe_allow_html=True)
        for key, label in NAV[user["role"]]:
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if key == page or (key == "seller_dashboard" and page == "listing_form") else "secondary"):
                h.go(key, selected_listing=None, editing_listing=None)
        st.divider()
        if st.button("Sign out", use_container_width=True):
            h.logout()
            st.rerun()


def allowed_pages(user):
    pages = {k for k, _ in NAV[user["role"]]}
    return pages | {"listing_form"} if user["role"] == h.ROLE_BUSINESS else pages


def main():
    st.set_page_config(page_title="FoodBridge", page_icon="🌿", layout="wide", initial_sidebar_state="auto")
    h.inject_css()
    user = h.current_user()
    page = st.session_state.get("page", "login")
    if user is None:
        page = page if page in h.PUBLIC_PAGES else "login"
    elif page in h.PUBLIC_PAGES or page not in allowed_pages(user):
        page = NAV[user["role"]][0][0]
    st.session_state["page"] = page
    if user:
        sidebar(user, page)
    PAGES[page]()


main()
