"""Shared UI helpers: backend access, session/login state, flash messages,
confirmation dialogs, formatting, validation and the global stylesheet."""
from __future__ import annotations

import html
import re
from datetime import datetime

import streamlit as st

from utils.demo_backend import (  # noqa: F401  (re-exported for the screens)
    BUYER_ORDER_TRANSITIONS, CATEGORIES, CONDITIONS, NGO_DONATION_TRANSITIONS, ROLE_BUSINESS, ROLE_NGO,
    SELLER_DONATION_TRANSITIONS, SELLER_ORDER_TRANSITIONS, UNITS, DemoBackend, ServiceError)

PUBLIC_PAGES = {"login", "register"}


# ------------------------------------------------------------------ backend
@st.cache_resource
def backend():
    """The single place the UI gets its backend from.

    Swap DemoBackend() for an adapter around services/*.py once Member 1's
    services exist; the method names it must offer are listed in
    utils/demo_backend.py.
    """
    return DemoBackend()


# ------------------------------------------------------------- session/auth
def current_user():
    return st.session_state.get("user")


def login_user(user):
    st.session_state["user"] = user


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def is_business() -> bool:
    return bool(current_user()) and current_user()["role"] == ROLE_BUSINESS


def go(page: str, **state):
    """Navigate to a page (optionally setting session keys first) and rerun."""
    st.session_state.update(state)
    st.session_state["page"] = page
    st.rerun()


# ---------------------------------------------------------- messages/dialogs
def flash(message: str, kind: str = "success"):
    st.session_state.setdefault("_flash", []).append((kind, message))


def show_flashes():
    for kind, message in st.session_state.pop("_flash", []):
        {"success": st.success, "error": st.error, "warning": st.warning}.get(kind, st.info)(
            message, icon={"success": "✅", "error": "⚠️", "warning": "⚠️"}.get(kind))


def show_errors(errors):
    for e in errors:
        st.error(e, icon="⚠️")


@st.dialog("Please confirm")
def _confirm_dialog(message, confirm_label, on_confirm, success_message):
    st.write(message)
    yes, no = st.columns(2)
    if yes.button(confirm_label, type="primary", use_container_width=True):
        try:
            on_confirm()
            flash(success_message)
        except ValueError as e:          # ServiceError is a ValueError
            flash(str(e), "error")
        st.rerun()
    if no.button("Go back", use_container_width=True):
        st.rerun()


def confirm_button(label, message, on_confirm, success_message, *, key, confirm_label="Yes, continue",
                   type="secondary", disabled=False, use_container_width=False):
    """A button that opens a confirmation dialog; on_confirm() runs only after 'yes'."""
    if st.button(label, key=key, type=type, disabled=disabled, use_container_width=use_container_width):
        _confirm_dialog(message, confirm_label, on_confirm, success_message)


# --------------------------------------------------------------- formatting
def esc(text) -> str:
    return html.escape(str(text))


def money(value) -> str:
    return f"₹{value:,.2f}".replace(".00", "")


def qty(value, unit="") -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".") + (f" {unit}" if unit else "")


def fmt_dt(dt) -> str:
    return dt.strftime("%a %d %b, %I:%M %p") if dt else "—"


def time_left(deadline) -> tuple[str, str]:
    """(label, tone) – tone is 'bad' when under 6h, 'warn' under 24h, else 'good'."""
    secs = (deadline - datetime.now()).total_seconds()
    if secs <= 0:
        return "Deadline passed", "muted"
    d, h, m = int(secs // 86400), int(secs % 86400 // 3600), int(secs % 3600 // 60)
    label = f"{d}d {h}h left" if d else f"{h}h {m}m left" if h else f"{m}m left"
    return label, "bad" if secs < 6 * 3600 else "warn" if secs < 24 * 3600 else "good"


_TONES = {"Available": "good", "Fresh": "good", "Good": "info", "Best used soon": "warn",
          "Sold out": "muted", "Expired": "muted", "Cancelled": "bad", "Rejected": "bad", "Declined": "bad",
          "Pending": "warn", "Requested": "warn", "Confirmed": "info", "Approved": "info",
          "Ready for collection": "info", "Completed": "good", "Collected": "good"}


def badge(text, tone=None) -> str:
    return f'<span class="fb-badge fb-{tone or _TONES.get(text, "muted")}">{esc(text)}</span>'


ORDER_STEPS = ["Pending", "Confirmed", "Ready for collection", "Completed"]
DONATION_STEPS = ["Requested", "Approved", "Collected"]


def status_steps(status, steps) -> str:
    """Small progress trail, e.g. Pending → [Confirmed] → Ready → Completed."""
    if status not in steps:
        return badge(status)
    cur = steps.index(status)
    parts = [f'<span class="fb-step {"fb-done" if i < cur else "fb-now" if i == cur else ""}">{esc(s)}</span>'
             for i, s in enumerate(steps)]
    return '<div class="fb-steps">' + '<span class="fb-arrow">›</span>'.join(parts) + "</div>"


def metric_row(items):
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)


# --------------------------------------------------------------- validation
def required_errors(**fields) -> list[str]:
    """required_errors(**{'Email': email, ...}) -> one message per blank field."""
    return [f"{label} is required." for label, value in fields.items() if not str(value or "").strip()]


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (email or "").strip()))


# --------------------------------------------------------------------- CSS
_CSS = """
<style>
.block-container{padding-top:2.2rem;max-width:1180px}
h1,h2,h3{letter-spacing:-.01em}
.fb-brand{font-size:1.45rem;font-weight:700;color:#1f6f4a;margin:0 0 .2rem}
.fb-sub{color:#6b6f66;font-size:.88rem;margin-bottom:.6rem}
.fb-title{font-weight:650;font-size:1.05rem}
.fb-head{display:flex;justify-content:space-between;align-items:flex-start;gap:.5rem}
.fb-price{font-size:1.35rem;font-weight:700;color:#1f6f4a;margin:.25rem 0}
.fb-price small{font-size:.8rem;font-weight:500;color:#6b6f66}
.fb-price s{font-size:.9rem;font-weight:400;color:#9a9d94;margin-left:.3rem}
.fb-off{font-size:.75rem;font-weight:650;color:#b45309;background:#fef3c7;border-radius:6px;padding:1px 6px;margin-left:.3rem}
.fb-meta{color:#4b4f47;font-size:.88rem;margin:.1rem 0}
.fb-badge{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.74rem;font-weight:600;white-space:nowrap}
.fb-good{background:#dcfce7;color:#166534}.fb-info{background:#dbeafe;color:#1e40af}
.fb-warn{background:#fef3c7;color:#92400e}.fb-bad{background:#fee2e2;color:#991b1b}
.fb-muted{background:#ececea;color:#55584f}
.fb-steps{display:flex;flex-wrap:wrap;align-items:center;gap:.25rem;font-size:.78rem;margin:.3rem 0}
.fb-step{color:#9a9d94}.fb-done{color:#1f6f4a}.fb-now{color:#fff;background:#1f6f4a;border-radius:999px;padding:1px 9px;font-weight:600}
.fb-arrow{color:#c3c5bd}
@media (max-width:640px){.block-container{padding:1.2rem .8rem}.fb-price{font-size:1.2rem}}
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)
