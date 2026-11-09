"""Market-segment tracking: one snapshot of asking-price stats per run, kept as a time series.

Segments are defined in config/segments.json and stored in data/<slug>.json as
{"segment": {...}, "snapshots": [{"date": ..., "count": ..., "median_ppm": ...}, ...]}.
"""

from __future__ import annotations

import re
import statistics
from datetime import date, timedelta

# "Prodej rodinného domu 135 m², pozemek 1375 m²" → 135
_TITLE_AREA = re.compile(r"(\d[\d\s\xa0]*)\s*m[²2]\s*,\s*pozemek", re.IGNORECASE)
BEFORE_RENOVATION = "před rekonstrukcí"


def usable_area(listing: dict, cache: dict) -> int | None:
    det = cache.get(listing["id"])
    if det and det.get("ok") and det.get("usable_area"):
        return det["usable_area"]
    m = _TITLE_AREA.search(listing.get("title") or "")
    return int(re.sub(r"\D", "", m.group(1))) if m else None


def segment_listings(area_data: dict, cache: dict, seg: dict) -> list[dict]:
    """Active listings in the segment, each as {"listing", "usable_area"}.

    Listings with unknown usable area are kept (they count for price stats);
    listings with a known area outside the range are dropped.
    """
    lo, hi = seg["price"]["min"], seg["price"]["max"]
    alo, ahi = seg["usable_area"]["min"], seg["usable_area"]["max"]
    out = []
    for l in area_data.get("listings", []):
        if l.get("status") != "active" or l.get("type") != seg["type"]:
            continue
        price = l.get("price")
        if not price or not (lo <= price <= hi):
            continue
        if (l.get("area_m2") or 0) < seg["plot_min"]:
            continue
        ua = usable_area(l, cache)
        if ua is not None and not (alo <= ua <= ahi):
            continue
        out.append({"listing": l, "usable_area": ua})
    return out


def _median(values: list[float]) -> int | None:
    return round(statistics.median(values)) if values else None


def _quartiles(values: list[float]) -> tuple[int | None, int | None]:
    if len(values) < 4:
        return None, None
    q = statistics.quantiles(values, n=4)
    return round(q[0]), round(q[2])


def snapshot(area_data: dict, cache: dict, seg: dict, today: str) -> dict:
    items = segment_listings(area_data, cache, seg)
    prices = [x["listing"]["price"] for x in items]
    ppm = [x["listing"]["price"] / x["usable_area"] for x in items if x["usable_area"]]
    ppm_before = [
        x["listing"]["price"] / x["usable_area"] for x in items
        if x["usable_area"] and (cache.get(x["listing"]["id"]) or {}).get("condition") == BEFORE_RENOVATION
    ]
    since = (date.fromisoformat(today) - timedelta(days=30)).isoformat()
    cuts = 0
    for x in items:
        hist = x["listing"].get("price_history") or []
        if len(hist) > 1 and hist[-1]["price"] < hist[0]["price"]:
            cuts += 1
    q1, q3 = _quartiles(ppm)

    by_id = {l["id"]: l for l in area_data.get("listings", [])}
    watch = {}
    for wid in seg.get("watch_ids", []):
        l = by_id.get(wid)
        watch[wid] = l.get("price") if l and l.get("status") == "active" else None

    return {
        "date": today,
        "count": len(items),
        "count_with_area": len(ppm),
        "median_price": _median(prices),
        "median_ppm": _median(ppm),
        "p25_ppm": q1,
        "p75_ppm": q3,
        "median_ppm_before_renovation": _median(ppm_before),
        "price_cuts": cuts,
        "new_30d": sum(1 for x in items if (x["listing"].get("added") or "") >= since),
        "watch": watch,
        "listings": {x["listing"]["id"]: x["listing"]["price"] for x in items},
    }


# house sub-types that count as family houses (no cottages, farmsteads, turnkey projects)
_FAMILY_SUBS = ("/dum/rodinny/", "/dum/vila/", "/dum/vicegeneracni-dum/")
_PLOT = re.compile(r"pozemek\s+(\d[\d\s\xa0]*)\s*m", re.IGNORECASE)


def district_area_data(raws: list) -> dict:
    """Turn Sreality district-wide raw listings into area-data shaped dict (active houses only)."""
    listings = []
    for r in raws:
        if not any(sub in r.url for sub in _FAMILY_SUBS):
            continue
        price = int(re.sub(r"\D", "", r.price_raw)) if r.price_raw else None
        m = _PLOT.search(r.title or "")
        listings.append({
            "id": f"sreality_{r.portal_id}",
            "type": "dum",
            "status": "active",
            "title": r.title,
            "url": r.url,
            "price": price,
            "area_m2": int(re.sub(r"\D", "", m.group(1))) if m else None,
            "added": None,
            "price_history": [],
        })
    return {"listings": listings}


def update_history(history: dict, snap: dict) -> dict:
    """Insert snap, replacing a snapshot from the same day; keep chronological order."""
    snaps = [s for s in history.get("snapshots", []) if s["date"] != snap["date"]]
    snaps.append(snap)
    history["snapshots"] = sorted(snaps, key=lambda s: s["date"])
    return history


def monthly(snapshots: list[dict]) -> list[dict]:
    """Last snapshot of each calendar month."""
    by_month: dict[str, dict] = {}
    for s in sorted(snapshots, key=lambda s: s["date"]):
        by_month[s["date"][:7]] = s
    return list(by_month.values())


def run_segments(today: str | None = None) -> list[dict]:
    """Snapshot every segment in config/segments.json into data/<slug>.json."""
    from src.config import CONFIG_DIR, load_area_data, load_json_data, save_json_data
    import json

    path = CONFIG_DIR / "segments.json"
    if not path.exists():
        return []
    today = today or date.today().isoformat()
    cache = load_json_data("details_cache", {})
    snaps = []
    for seg in json.loads(path.read_text()):
        if seg.get("source") == "sreality_district":
            snap = snapshot(_fetch_sreality_district(), cache, seg, today)
            snap["price_cuts"] = snap["new_30d"] = None  # no listing history for this source
        else:
            snap = snapshot(load_area_data(seg["area"]), cache, seg, today)
        history = load_json_data(seg["slug"], {})
        history["segment"] = seg
        save_json_data(seg["slug"], update_history(history, snap))
        print(f"  {seg['slug']}: {snap['count']} listings, median {snap['median_ppm']} Kč/m²")
        snaps.append(snap)
    return snaps


def _fetch_sreality_district() -> dict:
    import asyncio
    from src.scrapers.sreality import SrealityScraper

    return district_area_data(asyncio.run(SrealityScraper().scrape("dum")))
