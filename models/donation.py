"""DonationRequest dataclass – represents a row in the donation_requests table."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DonationRequest:
    id: int
    listing_id: int
    ngo_id: int
    seller_id: int
    quantity: float
    note: str
    status: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    # Populated by JOINs
    listing_name: str = ""
    unit: str = ""
    location: str = ""
    deadline: datetime | None = None
    ngo_name: str = ""
    seller_name: str = ""

    @classmethod
    def from_row(cls, row: dict) -> "DonationRequest":
        return cls(
            id=row["id"],
            listing_id=row["listing_id"],
            ngo_id=row["ngo_id"],
            seller_id=row["seller_id"],
            quantity=float(row.get("quantity", 0) or 0),
            note=row.get("note", ""),
            status=row["status"],
            created_at=row.get("created_at") or datetime.utcnow(),
            updated_at=row.get("updated_at") or datetime.utcnow(),
            completed_at=row.get("completed_at"),
            listing_name=row.get("listing_name", ""),
            unit=row.get("unit", ""),
            location=row.get("location", ""),
            deadline=row.get("deadline"),
            ngo_name=row.get("ngo_name", ""),
            seller_name=row.get("seller_name", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "listing_id": self.listing_id,
            "ngo_id": self.ngo_id,
            "seller_id": self.seller_id,
            "quantity": self.quantity,
            "note": self.note,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "listing_name": self.listing_name,
            "unit": self.unit,
            "location": self.location,
            "deadline": self.deadline,
            "ngo_name": self.ngo_name,
            "seller_name": self.seller_name,
        }
