"""Diff current scrape results against previous data to detect changes."""

from datetime import date


def diff_listings(
    prev_data: dict,
    current_dicts: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Compare current scrape with previous data.

    Returns: (new, price_changed, removed, unchanged)
    - new: listings not in previous data
    - price_changed: listings with different price (price_history updated)
    - removed: previously active listings not in current scrape (status set to removed)
    - unchanged: listings identical to previous
    """
    today = date.today().isoformat()

    # Index previous listings by ID
    prev_by_id: dict[str, dict] = {}
    for listing in prev_data.get("listings", []):
        prev_by_id[listing["id"]] = listing

    # Index current listings by ID
    current_by_id: dict[str, dict] = {}
    for listing in current_dicts:
        current_by_id[listing["id"]] = listing

    new = []
    changed = []
    unchanged = []

    for lid, curr in current_by_id.items():
        prev = prev_by_id.get(lid)
        if prev is None:
            # New listing
            new.append(curr)
        elif prev.get("price") != curr.get("price") and curr.get("price") is not None:
            # Price changed — merge with previous data, append to history
            merged = {**prev, **curr}
            merged["added"] = prev.get("added", today)
            merged["updated"] = today
            merged["status"] = "active"
            merged["removed_date"] = None
            history = list(prev.get("price_history", []))
            history.append({"date": today, "price": curr["price"]})
            merged["price_history"] = history
            changed.append(merged)
        else:
            # Unchanged — keep previous data (preserves added date, history)
            kept = {**prev}
            kept["status"] = "active"
            kept["removed_date"] = None
            unchanged.append(kept)

    # Removed: in previous but not in current, and was active
    removed = []
    for lid, prev in prev_by_id.items():
        if lid not in current_by_id:
            if prev.get("status") == "active":
                marked = {**prev, "status": "removed", "removed_date": today}
                removed.append(marked)
            else:
                # Already removed — keep as-is
                unchanged.append(prev)

    return new, changed, removed, unchanged
