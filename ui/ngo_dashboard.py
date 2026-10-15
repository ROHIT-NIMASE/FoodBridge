"""NGO dashboard: eligible donation offers and a quick request form."""
import streamlit as st

from utils import helpers as h


def render():
    user = h.current_user()
    be = h.backend()
    st.title("Donation offers")
    st.caption("Surplus that sellers have offered to NGOs. These items are unsold and close to their collection deadline.")
    h.show_flashes()

    offers = be.donation_offers()
    mine = be.ngo_requests(user["id"])
    h.metric_row([("Available offers", len(offers)),
                  ("Awaiting approval", sum(r["status"] == "Requested" for r in mine)),
                  ("Approved – ready to collect", sum(r["status"] == "Approved" for r in mine)),
                  ("Collected", sum(r["status"] == "Collected" for r in mine))])

    if not offers:
        st.info("No eligible donation offers right now. Check back soon.")
        return
    for l in offers:
        left, tone = h.time_left(l["deadline"])
        with st.container(border=True):
            st.markdown("".join([
                f'<div class="fb-head"><span class="fb-title">{h.esc(l["name"])}</span>{h.badge(l["condition"])}</div>',
                f'<div class="fb-meta">📦 {h.qty(l["quantity_available"], l["unit"])} available · '
                f'📍 {h.esc(l["location"])}</div>',
                f'<div class="fb-meta">🏪 {h.esc(l["seller_name"])} · ⏰ Collect by {h.fmt_dt(l["deadline"])} '
                f'{h.badge(left, tone)}</div>']), unsafe_allow_html=True)
            with st.expander("Request this donation"):
                amount = st.number_input(f"Quantity needed ({l['unit']})", min_value=0.0,
                                         max_value=float(l["quantity_available"]),
                                         value=min(1.0, float(l["quantity_available"])), step=1.0,
                                         key=f"don_qty_{l['id']}")
                note = st.text_input("Note to donor (optional)", key=f"don_note_{l['id']}",
                                     placeholder="Pickup person, vehicle, timing…")
                h.confirm_button(
                    "Send request",
                    f"Request {h.qty(amount, l['unit'])} of {l['name']} from {l['seller_name']}?",
                    lambda l=l, amount=amount, note=note: be.request_donation(l["id"], user["id"], amount, note),
                    "Donation request sent. The donor will review it.",
                    key=f"don_send_{l['id']}", type="primary", confirm_label="Send request", disabled=amount <= 0)
