"""Registration screen for businesses and NGOs."""
import streamlit as st

from utils import helpers as h

ACCOUNT_TYPES = {"Business (sell or buy ingredients)": h.ROLE_BUSINESS, "NGO (receive donations)": h.ROLE_NGO}


def render():
    _, centre, _ = st.columns([1, 2, 1])
    with centre:
        st.markdown('<div class="fb-brand">🌿 FoodBridge</div>', unsafe_allow_html=True)
        st.subheader("Create your account")
        with st.form("register_form"):
            account = st.radio("I am registering as", list(ACCOUNT_TYPES), horizontal=False)
            org = st.text_input("Organisation name")
            name = st.text_input("Your name")
            email = st.text_input("Email")
            phone = st.text_input("Phone (optional)")
            location = st.text_input("Location", placeholder="Area, City")
            password = st.text_input("Password", type="password", help="At least 8 characters")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if submitted:
            errors = h.required_errors(**{"Organisation name": org, "Your name": name, "Email": email,
                                          "Location": location, "Password": password,
                                          "Confirm password": confirm})
            if email.strip() and not h.valid_email(email):
                errors.append("Enter a valid email address.")
            if password and len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            if password and confirm and password != confirm:
                errors.append("Passwords do not match.")
            if errors:
                h.show_errors(errors)
            else:
                try:
                    h.backend().register_user(name, email, password, ACCOUNT_TYPES[account], org, location, phone)
                except ValueError as e:
                    st.error(str(e), icon="⚠️")
                else:
                    h.flash("Account created. Sign in to get started.")
                    h.go("login")
        if st.button("Already have an account? Sign in", use_container_width=True):
            h.go("login")
