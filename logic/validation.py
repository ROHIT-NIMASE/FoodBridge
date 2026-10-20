"""Shared input and business-rule validation for FoodBridge.

All validators raise ServiceError (a ValueError) with a user-safe message,
matching the same contract as DemoBackend.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from utils.demo_backend import (  # noqa: F401 – re-use constants from the contract
    CATEGORIES, CONDITIONS, UNITS, ServiceError,
)

# ------------------------------------------------------------------ primitives
def require_str(value: Any, label: str) -> str:
    s = str(value or "").strip()
    if not s:
        raise ServiceError(f"{label} is required.")
    return s


def require_positive(value: Any, label: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ServiceError(f"{label} must be a number.")
    if f <= 0:
        raise ServiceError(f"{label} must be greater than zero.")
    return f


def require_email(email: str) -> str:
    email = str(email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ServiceError("Enter a valid email address.")
    return email


# ------------------------------------------------------------------ compound
def validate_registration(name, email, password, confirm, role, org_name, location):
    """Collect all errors then raise once, so the UI can show them all."""
    errors: list[str] = []
    for field_val, label in [(name, "Your name"), (org_name, "Organisation name"), (location, "Location")]:
        if not str(field_val or "").strip():
            errors.append(f"{label} is required.")
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append("Enter a valid email address.")
    if not str(password or ""):
        errors.append("Password is required.")
    elif len(str(password)) < 8:
        errors.append("Password must be at least 8 characters.")
    if not str(confirm or ""):
        errors.append("Confirm password is required.")
    elif str(password or "") and str(password) != str(confirm or ""):
        errors.append("Passwords do not match.")
    if role not in ("business", "ngo"):
        errors.append("Choose an account type.")
    if errors:
        raise ServiceError(" ".join(errors))
    return email


def validate_listing(data: dict) -> dict:
    """Validate and normalise a listing data dict.  Returns clean fields."""
    errors: list[str] = []
    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("Ingredient name is required.")
    location = str(data.get("location") or "").strip()
    if not location:
        errors.append("Location is required.")

    nums: dict[str, float] = {}
    for key, label in (("quantity", "Quantity"), ("price", "Price per unit")):
        try:
            nums[key] = require_positive(data.get(key), label)
        except ServiceError as exc:
            errors.append(str(exc))

    original = data.get("original_price")
    if original in (None, "", 0):
        original = nums.get("price")
    else:
        try:
            original = require_positive(original, "Original price")
        except ServiceError as exc:
            errors.append(str(exc))
            original = None
    if original and nums.get("price") and original < nums["price"]:
        errors.append("Original price cannot be lower than the discounted price.")

    deadline = data.get("deadline")
    if not isinstance(deadline, datetime):
        errors.append("Collection deadline is required.")
    elif deadline <= datetime.now():
        errors.append("Collection deadline must be in the future.")

    category  = data.get("category", "Other")
    condition = data.get("condition", "Fresh")
    unit      = data.get("unit", "kg")
    if category not in CATEGORIES:
        errors.append("Choose a valid category.")
    if condition not in CONDITIONS:
        errors.append("Choose a valid condition.")
    if unit not in UNITS:
        errors.append("Choose a valid unit.")

    if errors:
        raise ServiceError(" ".join(errors))

    return {
        "name": name,
        "category": category,
        "quantity": nums["quantity"],
        "unit": unit,
        "price": nums["price"],
        "original_price": original,
        "condition": condition,
        "location": location,
        "deadline": deadline,
        "description": str(data.get("description") or "").strip(),
        "donate_if_unsold": bool(data.get("donate_if_unsold")),
    }
