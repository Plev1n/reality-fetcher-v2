"""Simple market comparison from the monitored area data."""

from __future__ import annotations

import statistics

MIN_PLAUSIBLE_PRICE = 500_000  # filters out rents / per-m² prices mislabelled as totals


def _stats(prices: list[int]) -> dict:
    if not prices:
        return {"count": 0}
    return {"count": len(prices), "median": int(statistics.median(prices)), "min": min(prices), "max": max(prices)}


def market_stats(area_data: dict, location_id: str, listing_type: str = "dum") -> dict:
    prices_all, prices_loc = [], []
    for l in area_data.get("listings", []):
        if l.get("type") != listing_type or l.get("status") != "active":
            continue
        p = l.get("price")
        if not p or p < MIN_PLAUSIBLE_PRICE:
            continue
        prices_all.append(p)
        if l.get("location_id") == location_id:
            prices_loc.append(p)
    return {"locality": _stats(prices_loc), "area": _stats(prices_all)}
