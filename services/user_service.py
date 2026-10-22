"""User service – registration, authentication, and user retrieval.

All methods raise ServiceError (a ValueError subclass) with a safe user-facing
message, matching the DemoBackend contract.
"""
from __future__ import annotations

from database.database import query_one, query_all, execute, transaction
from logic.validation import validate_registration, ServiceError
from models.user import User
from utils.security import hash_password, verify_password


# ------------------------------------------------------------------ public API
def register_user(
    name: str,
    email: str,
    password: str,
    confirm: str,
    role: str,
    org_name: str,
    location: str,
    phone: str = "",
) -> dict:
    """Create a new user.  Returns a public user dict on success."""
    clean_email = validate_registration(name, email, password, confirm, role, org_name, location)

    existing = query_one("SELECT id FROM users WHERE email = %s", (clean_email,))
    if existing:
        raise ServiceError("An account with this email already exists.")

    pw_hash = hash_password(password)
    user_id = execute(
        """
        INSERT INTO users (organisation_name, name, email, password_hash, role, location, phone)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (org_name.strip(), name.strip(), clean_email, pw_hash, role, location.strip(), (phone or "").strip()),
    )

    # For NGO accounts, also create an ngos row
    if role == "ngo":
        execute(
            """
            INSERT INTO ngos (user_id, organisation_name, contact_person, location)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, org_name.strip(), name.strip(), location.strip()),
        )

    row = query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    return _public_dict(row)


def authenticate(email: str, password: str) -> dict | None:
    """Return a public user dict if credentials are correct, else None."""
    email = (email or "").strip().lower()
    row = query_one(
        "SELECT * FROM users WHERE email = %s AND is_active = 1",
        (email,),
    )
    if row and verify_password(password or "", row["password_hash"]):
        return _public_dict(row)
    return None


def get_user(user_id: int) -> dict | None:
    """Return a public user dict by id, or None."""
    row = query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    return _public_dict(row) if row else None


def get_all_users() -> list[dict]:
    rows = query_all("SELECT * FROM users ORDER BY created_at DESC")
    return [_public_dict(r) for r in rows]


# ------------------------------------------------------------------ internal
def _public_dict(row: dict) -> dict:
    """Strip sensitive fields and normalise key names for the UI."""
    u = User.from_row(row)
    return u.to_public_dict()
