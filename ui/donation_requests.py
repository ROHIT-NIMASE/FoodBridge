"""NGO donation requests, plus the shared request row used by the seller dashboard."""
import streamlit as st

from utils import helpers as h


def request_row(req, perspective: str):
    """perspective: 'ngo' (can cancel) or 'seller' (can approve / decline / mark collected)."""
    user = h.current_user()
    transitions = h.NGO_DONATION_TRANSITIONS if perspective == "ngo" else h.SELLER_DONATION_TRANSITIONS
    other = req["seller_name"] if perspective == "ngo" else req["ngo_name"]
    with st.container(border=True):
        st.markdown(f'<span class="fb-title">{h.esc(req["listing_name"])}</span> '
                    f'× {h.qty(req["quantity"], req["unit"])} {h.badge(req["status"])}', unsafe_allow_html=True)
        st.markdown(h.status_steps(req["status"], h.DONATION_STEPS), unsafe_allow_html=True)
        st.markdown(
            f'<div class="fb-meta">{"🏪 Donor" if perspective == "ngo" else "🤝 NGO"}: {h.esc(other)} · '
            f'📍 {h.esc(req["location"])} · ⏰ Collect by {h.fmt_dt(req["deadline"])}</div>'
            f'<div class="fb-meta">Request #{req["id"]} · sent {h.fmt_dt(req["created_at"])}</div>',
            unsafe_allow_html=True)
        if req["note"]:
            st.caption(f"Note: {req['note']}")
        actions = transitions.get(req["status"], [])
        if actions:
            cols = st.columns(len(actions) + 1)
            for col, new_status in zip(cols, actions):
                negative = new_status in ("Cancelled", "Declined")
                label = {"Cancelled": "Cancel request", "Declined": "Decline", "Approved": "Approve",
                         "Collected": "Mark collected"}[new_status]
                with col:
                    h.confirm_button(
                        label, f"{label} for request #{req['id']} ({req['listing_name']})?",
                        lambda s=new_status: h.backend().set_donation_status(req["id"], user["id"], s),
                        f"Request #{req['id']} is now {new_status.lower()}.",
                        key=f"{perspective}_don_{req['id']}_{new_status}",
                        type="secondary" if negative else "primary", confirm_label="Yes, confirm",
                        use_container_width=True)


def render():
    user = h.current_user()
    st.title("My donation requests")
    h.show_flashes()
    requests = h.backend().ngo_requests(user["id"])
    if not requests:
        st.info("You haven't requested any donations yet.")
        if st.button("See available donation offers", type="primary"):
            h.go("ngo_dashboard")
        return
    status = st.selectbox("Status", ["All", "Requested", "Approved", "Collected", "Declined", "Cancelled"])
    shown = [r for r in requests if status == "All" or r["status"] == status]
    st.caption(f"Showing {len(shown)} of {len(requests)} requests")
    for r in shown:
        request_row(r, "ngo")
    if not shown:
        st.info("No requests with that status.")
