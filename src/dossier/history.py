"""Listing history across portals, from current data files and git history of data/."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.pipeline.normalizer import strip_diacritics


def _fold(s: str | None) -> str:
    return strip_diacritics(s or "").lower()


def match_history(target: dict, locality_name: str | None, plot_area: int | None, pool: list[dict]) -> list[dict]:
    """Listings in `pool` that are very likely the same property as `target`.

    Same id, or same price plus (same locality id, locality name in title, or same plot area).
    Sorted by first-seen date, deduplicated by id.
    """
    price = target.get("price")
    loc_id = target.get("location_id")
    name = _fold(locality_name)
    seen: dict[str, dict] = {}
    for item in pool:
        same = item.get("id") == target.get("id")
        if not same and price and item.get("price") == price and item.get("type", "dum") == target.get("type", "dum"):
            same = (
                (loc_id and item.get("location_id") == loc_id)
                or (name and name in _fold(item.get("title")))
                or (plot_area and item.get("area_m2") == plot_area)
            )
        if same and item.get("id") not in seen:
            seen[item["id"]] = item
    return sorted(seen.values(), key=lambda x: (x.get("added") or "", x.get("id")))


def history_pool(repo_root: Path, area_slug: str, sample_every: int = 5) -> list[dict]:
    """All listings from the current data file plus a sample of past versions in git."""
    path = repo_root / "data" / f"{area_slug}.json"
    pool: dict[str, dict] = {}
    if path.exists():
        for l in json.loads(path.read_text()).get("listings", []):
            pool[l["id"]] = l
    try:
        commits = subprocess.run(
            ["git", "log", "--format=%h", "--", f"data/{area_slug}.json"],
            cwd=repo_root, capture_output=True, text=True, timeout=30,
        ).stdout.split()
    except Exception:
        commits = []
    for c in commits[::sample_every] + commits[-1:]:
        try:
            raw = subprocess.run(["git", "show", f"{c}:data/{area_slug}.json"], cwd=repo_root,
                                 capture_output=True, text=True, timeout=30).stdout
            for l in json.loads(raw).get("listings", []):
                pool.setdefault(l["id"], l)
        except Exception:
            continue
    return list(pool.values())
