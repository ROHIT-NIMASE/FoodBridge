"""User dataclass – thin wrapper around a users-table row dict."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    id: int
    organisation_name: str
    name: str
    email: str
    role: str                # 'business' | 'ngo'
    location: str
    phone: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ------------------------------------------------------------------
    @classmethod
    def from_row(cls, row: dict) -> "User":
        """Construct from a database dict.  Ignores unknown keys."""
        return cls(
            id=row["id"],
            organisation_name=row.get("organisation_name", row.get("org_name", "")),
            name=row["name"],
            email=row["email"],
            role=row["role"],
            location=row["location"],
            phone=row.get("phone", ""),
            is_active=bool(row.get("is_active", True)),
            created_at=row.get("created_at") or datetime.utcnow(),
            updated_at=row.get("updated_at") or datetime.utcnow(),
        )

    def to_public_dict(self) -> dict:
        """Dict safe to return to the UI (no password fields)."""
        return {
            "id": self.id,
            "name": self.name,
            "org_name": self.organisation_name,     # UI uses org_name
            "organisation_name": self.organisation_name,
            "email": self.email,
            "role": self.role,
            "location": self.location,
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }
