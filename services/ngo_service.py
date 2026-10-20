"""NGO service – NGO profile retrieval and management."""
from __future__ import annotations

from database.database import query_one, query_all
from models.ngo import NGO
from utils.demo_backend import ServiceError


def get_ngo_by_user(user_id: int) -> dict | None:
    """Return the NGO profile dict for a given user_id, or None."""
    row = query_one("SELECT * FROM ngos WHERE user_id = %s", (user_id,))
    return NGO.from_row(row).to_dict() if row else None


def get_ngo(ngo_id: int) -> dict | None:
    row = query_one("SELECT * FROM ngos WHERE id = %s", (ngo_id,))
    return NGO.from_row(row).to_dict() if row else None


def list_ngos() -> list[dict]:
    rows = query_all("SELECT * FROM ngos ORDER BY organisation_name")
    return [NGO.from_row(r).to_dict() for r in rows]
