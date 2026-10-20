"""Matching logic – find the best NGO donation candidates for a listing."""
from __future__ import annotations

from logic.donation_logic import is_donation_eligible


def eligible_donation_listings(listings: list[dict]) -> list[dict]:
    """Filter and sort a list of listing-view-dicts for the NGO donation board."""
    eligible = [l for l in listings if l.get("donation_eligible")]
    return sorted(eligible, key=lambda x: x["deadline"])


def match_listings_to_query(
    listings: list[dict],
    query: str = "",
    location: str = "",
    category: str | None = None,
    conditions: list[str] | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: float | None = None,
    sort: str = "Collect-by soonest",
) -> list[dict]:
    """Filter and sort marketplace listings.

    Mirrors the logic in DemoBackend.search_listings exactly so that
    swapping backends produces identical results.
    """
    q = (query or "").strip().lower()
    loc = (location or "").strip().lower()
    out = []
    for v in listings:
        if v["status"] != "Available":
            continue
        if q and q not in " ".join([v["name"], v["category"], v["description"]]).lower():
            continue
        if loc and loc not in v["location"].lower():
            continue
        if category and category != "All" and v["category"] != category:
            continue
        if conditions and v["condition"] not in conditions:
            continue
        if min_price is not None and v["price"] < min_price:
            continue
        if max_price is not None and v["price"] > max_price:
            continue
        if min_quantity and v["quantity_available"] < min_quantity:
            continue
        out.append(v)

    keys = {
        "Collect-by soonest":   lambda x: x["deadline"],
        "Price: low to high":   lambda x: x["price"],
        "Price: high to low":   lambda x: -x["price"],
        "Quantity: most first": lambda x: -x["quantity_available"],
        "Biggest discount":     lambda x: -x["discount_pct"],
    }
    return sorted(out, key=keys.get(sort, keys["Collect-by soonest"]))
