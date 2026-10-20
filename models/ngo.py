"""NGO dataclass – represents a row in the ngos table."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NGO:
    id: int
    user_id: int
    organisation_name: str
    contact_person: str
    location: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_row(cls, row: dict) -> "NGO":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            organisation_name=row["organisation_name"],
            contact_person=row.get("contact_person", ""),
            location=row["location"],
            created_at=row.get("created_at") or datetime.utcnow(),
            updated_at=row.get("updated_at") or datetime.utcnow(),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organisation_name": self.organisation_name,
            "contact_person": self.contact_person,
            "location": self.location,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
