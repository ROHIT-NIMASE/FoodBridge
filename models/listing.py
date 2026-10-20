"""SurplusListing dataclass – represents a row in the surplus_listings table."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

DONATION_WINDOW_HOURS = 48  # hours before deadline when donation becomes eligible


@dataclass
class SurplusListing:
    id: int
    seller_id: int
    name: str
    category: str
    description: str
    total_quantity: float
    available_quantity: float
    unit: str
    discounted_price: float
    market_price: float
    condition_grade: str
    location: str
    collection_deadline: datetime
    donation_enabled: bool
    status: str               # DB status: available | sold_out | cancelled | expired
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Extra fields populated by JOINs in service layer
    seller_name: str = ""
    seller_location: str = ""

    # ------------------------------------------------------------------
    @classmethod
    def from_row(cls, row: dict) -> "SurplusListing":
        return cls(
            id=row["id"],
            seller_id=row["seller_id"],
            name=row["name"],
            category=row["category"],
            description=row.get("description", ""),
            total_quantity=float(row.get("total_quantity", 0) or 0),
            available_quantity=float(row.get("available_quantity", 0) or 0),
            unit=row["unit"],
            discounted_price=float(row.get("discounted_price", 0) or 0),
            market_price=float(row.get("market_price", 0) or 0),
            condition_grade=row.get("condition_grade", "Fresh"),
            location=row["location"],
            collection_deadline=row["collection_deadline"],
            donation_enabled=bool(row.get("donation_enabled", False)),
            status=row.get("status", "available"),
            created_at=row.get("created_at") or datetime.utcnow(),
            updated_at=row.get("updated_at") or datetime.utcnow(),
            seller_name=row.get("seller_name", ""),
            seller_location=row.get("seller_location", ""),
        )

    # ------------------------------------------------------------------
    def computed_status(self) -> str:
        """Derive the display status from DB state + current time."""
        if self.status == "cancelled":
            return "Cancelled"
        now = datetime.utcnow()
        if self.collection_deadline <= now:
            return "Expired"
        if self.available_quantity <= 0:
            return "Sold out"
        return "Available"

    def donation_eligible(self) -> bool:
        now = datetime.utcnow()
        return (
            self.computed_status() == "Available"
            and self.donation_enabled
            and self.collection_deadline <= now + timedelta(hours=DONATION_WINDOW_HOURS)
        )

    def discount_pct(self) -> int:
        orig = self.market_price or self.discounted_price
        if not orig:
            return 0
        return round((1 - self.discounted_price / orig) * 100)

    def reserved(self) -> float:
        return self.total_quantity - self.available_quantity

    def to_view_dict(self) -> dict:
        """Return the dict shape the UI screens expect (mirrors DemoBackend._view_listing)."""
        return {
            "id": self.id,
            "seller_id": self.seller_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "quantity": self.total_quantity,
            "quantity_available": self.available_quantity,
            "reserved": self.reserved(),
            "unit": self.unit,
            "price": self.discounted_price,
            "original_price": self.market_price,
            "condition": self.condition_grade,
            "location": self.location,
            "deadline": self.collection_deadline,
            "donate_if_unsold": self.donation_enabled,
            "status": self.computed_status(),
            "seller_name": self.seller_name,
            "seller_location": self.seller_location,
            "donation_eligible": self.donation_eligible(),
            "discount_pct": self.discount_pct(),
            "created_at": self.created_at,
            "cancelled": self.status == "cancelled",
        }
