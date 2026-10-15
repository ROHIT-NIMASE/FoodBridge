"""Sign-in screen."""
import streamlit as st

from utils import helpers as h


def render():
    _, centre, _ = st.columns([1, 2, 1])
    with centre:
        st.markdown('<div class="fb-brand">🌿 FoodBridge</div>'
                    '<div class="fb-sub">Surplus ingredients, resold fairly or donated before they go to waste.</div>',
                    unsafe_allow_html=True)
        st.subheader("Sign in")
        h.show_flashes()
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@business.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            errors = h.required_errors(Email=email, Password=password)
            if not errors and not h.valid_email(email):
                errors.append("Enter a valid email address.")
            if errors:
                h.show_errors(errors)
            else:
                user = h.backend().authenticate(email, password)
                if user is None:
                    st.error("Incorrect email or password.", icon="⚠️")
                else:
                    h.login_user(user)
                    h.flash(f"Welcome back, {user['name'].split()[0]}!")
                    h.go("ngo_dashboard" if user["role"] == h.ROLE_NGO else "marketplace")
        if st.button("New here? Create an account", use_container_width=True):
            h.go("register")
        with st.expander("Demo accounts (password: demo1234)"):
            st.markdown("- **Seller:** seller@demo.com or bakery@demo.com\n"
                        "- **Buyer:** buyer@demo.com\n- **NGO:** ngo@demo.com")
