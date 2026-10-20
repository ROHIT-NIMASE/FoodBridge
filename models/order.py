"""Order dataclass – represents a row in the orders table."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Order:
    id: int
    listing_id: int
    buyer_id: int
    seller_id: int
    quantity: float
    unit_price: float
    total: float
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
    buyer_name: str = ""
    seller_name: str = ""

    @classmethod
    def from_row(cls, row: dict) -> "Order":
        return cls(
            id=row["id"],
            listing_id=row["listing_id"],
            buyer_id=row["buyer_id"],
            seller_id=row["seller_id"],
            quantity=float(row.get("quantity", 0) or 0),
            unit_price=float(row.get("unit_price", 0) or 0),
            total=float(row.get("total", 0) or 0),
            note=row.get("note", ""),
            status=row["status"],
            created_at=row.get("created_at") or datetime.utcnow(),
            updated_at=row.get("updated_at") or datetime.utcnow(),
            completed_at=row.get("completed_at"),
            listing_name=row.get("listing_name", ""),
            unit=row.get("unit", ""),
            location=row.get("location", ""),
            deadline=row.get("deadline"),
            buyer_name=row.get("buyer_name", ""),
            seller_name=row.get("seller_name", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "listing_id": self.listing_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total": self.total,
            "note": self.note,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "listing_name": self.listing_name,
            "unit": self.unit,
            "location": self.location,
            "deadline": self.deadline,
            "buyer_name": self.buyer_name,
            "seller_name": self.seller_name,
        }
