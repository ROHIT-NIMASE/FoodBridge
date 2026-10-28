
"""Matching logic for FoodBridge marketplace and NGO redistribution."""

from __future__ import annotations

from logic.donation_logic import is_donation_eligible


def eligible_donation_listings(listings: list[dict]) -> list[dict]:
    """Filter and sort listings eligible for the NGO donation board."""

    eligible = [listing for listing in listings
                if listing.get("donation_eligible")]

    return sorted(
        eligible,
        key=lambda listing: listing["deadline"],
    )


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
    """Filter and sort marketplace listings."""

    q = (query or "").strip().lower()
    loc = (location or "").strip().lower()
    results = []

    for listing in listings:
        if listing.get("status") != "Available":
            continue

        searchable = " ".join([
            str(listing.get("name", "")),
            str(listing.get("category", "")),
            str(listing.get("description", "")),
        ]).lower()

        if q and q not in searchable:
            continue

        if loc and loc not in str(listing.get("location", "")).lower():
            continue

        if category and category != "All":
            if listing.get("category") != category:
                continue

        if conditions and listing.get("condition") not in conditions:
            continue

        price = listing.get("price", 0)
        quantity = listing.get("quantity_available", 0)

        if min_price is not None and price < min_price:
            continue

        if max_price is not None and price > max_price:
            continue

        if min_quantity is not None and quantity < min_quantity:
            continue

        results.append(listing)

    sort_keys = {
        "Collect-by soonest": lambda item: item["deadline"],
        "Price: low to high": lambda item: item["price"],
        "Price: high to low": lambda item: -item["price"],
        "Quantity: most first": lambda item: -item["quantity_available"],
        "Biggest discount": lambda item: -item["discount_pct"],
    }

    return sorted(
        results,
        key=sort_keys.get(sort, sort_keys["Collect-by soonest"]),
    )


def match_ngos(listing, ngos):
    """Match a verified surplus listing with suitable NGOs."""

    if not listing.get("food_safety_verified", False):
        return []

    ingredient = str(listing.get("ingredient", "")).strip().lower()
    location = str(listing.get("location", "")).strip().lower()
    quantity = listing.get("quantity", 0)

    if not ingredient or not location or quantity <= 0:
        return []

    matches = []

    for ngo in ngos:
        accepted = [
            str(item).strip().lower()
            for item in ngo.get("accepted_ingredients", [])
        ]

        ngo_location = str(ngo.get("location", "")).strip().lower()
        capacity = ngo.get("max_quantity", 0)

        if (
            ingredient in accepted
            and location == ngo_location
            and capacity >= quantity
        ):
            matches.append(ngo)

    return matches
