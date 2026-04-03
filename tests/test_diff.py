# tests/test_diff.py
from src.diff import diff_listings


def test_new_listing():
    prev = {"listings": []}
    current = [{"id": "sreality_1", "price": 5000000, "status": "active"}]
    new, changed, removed, unchanged = diff_listings(prev, current)
    assert len(new) == 1
    assert new[0]["id"] == "sreality_1"
    assert changed == []
    assert removed == []


def test_price_change():
    prev = {"listings": [
        {"id": "sreality_1", "price": 5000000, "status": "active", "added": "2026-03-01",
         "price_history": [{"date": "2026-03-01", "price": 5000000}], "removed_date": None}
    ]}
    current = [{"id": "sreality_1", "price": 4500000, "status": "active"}]
    new, changed, removed, unchanged = diff_listings(prev, current)
    assert len(changed) == 1
    assert changed[0]["price"] == 4500000
    assert len(changed[0]["price_history"]) == 2


def test_removed_listing():
    prev = {"listings": [
        {"id": "sreality_1", "price": 5000000, "status": "active", "added": "2026-03-01",
         "price_history": [{"date": "2026-03-01", "price": 5000000}], "removed_date": None}
    ]}
    current = []  # Listing gone
    new, changed, removed, unchanged = diff_listings(prev, current)
    assert len(removed) == 1
    assert removed[0]["status"] == "removed"
    assert removed[0]["removed_date"] is not None


def test_unchanged_listing():
    prev = {"listings": [
        {"id": "sreality_1", "price": 5000000, "status": "active", "added": "2026-03-01",
         "price_history": [{"date": "2026-03-01", "price": 5000000}], "removed_date": None}
    ]}
    current = [{"id": "sreality_1", "price": 5000000, "status": "active"}]
    new, changed, removed, unchanged = diff_listings(prev, current)
    assert len(unchanged) == 1
    assert new == []
    assert changed == []


def test_already_removed_stays_removed():
    prev = {"listings": [
        {"id": "sreality_1", "price": 5000000, "status": "removed", "added": "2026-03-01",
         "price_history": [], "removed_date": "2026-03-28"}
    ]}
    current = []
    new, changed, removed, unchanged = diff_listings(prev, current)
    # Already removed — not counted as newly removed
    assert removed == []
    assert len(unchanged) == 1
