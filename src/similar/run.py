"""Find listings similar to a profile: select → fetch details (cached) → score."""

from __future__ import annotations

import asyncio
import random
from datetime import date, datetime, timezone

import httpx

from src.scrapers.base import BaseScraper
from src.similar.details import ListingDetails, details_from_dict, details_to_dict, fetch_details
from src.similar.scoring import score_listing

DASHBOARD_BASE_URL = "https://plev1n.github.io/reality-fetcher-v2"

LISTING_KEYS = ("id", "title", "url", "portal", "price", "location", "location_id",
                "added", "price_history", "area_m2", "coordinates")


def select_candidates(area_data: dict, profile: dict) -> list[dict]:
    """Active listings of the profile type with price inside the range (or unknown)."""
    lo, hi = profile["price"]["min"], profile["price"]["max"]
    out = []
    for listing in area_data.get("listings", []):
        if listing.get("status") != "active" or listing.get("type") != profile["type"]:
            continue
        price = listing.get("price")
        if price is not None and not (lo <= price <= hi):
            continue
        out.append(listing)
    return out


def _needs_fetch(cached: dict | None, today: str) -> bool:
    if cached is None:
        return True
    # failed fetches are retried on a later day, successful ones are kept
    return not cached.get("ok", False) and cached.get("fetched") != today


async def update_similar(
    area_data: dict,
    profile: dict,
    cache: dict,
    prev_result: dict,
    fetcher=fetch_details,
    max_fetch: int = 40,
    delay: float | None = None,
) -> dict:
    """Score candidates, fetching up to max_fetch missing details. Mutates `cache`."""
    today = date.today().isoformat()
    candidates = select_candidates(area_data, profile)
    to_fetch = [c for c in candidates if _needs_fetch(cache.get(c["id"]), today)][:max_fetch]

    if to_fetch:
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True,
            headers={"User-Agent": random.choice(BaseScraper.USER_AGENTS)},
        ) as client:
            for i, listing in enumerate(to_fetch):
                try:
                    det = await fetcher(listing["url"], client)
                except Exception:
                    det = ListingDetails(url=listing["url"], fetched=today, ok=False)
                cache[listing["id"]] = details_to_dict(det)
                if i < len(to_fetch) - 1:
                    await asyncio.sleep(random.uniform(1.0, 2.5) if delay is None else delay)

    # First run: everything found becomes the baseline, nothing is announced as new.
    first_run = "matches" not in prev_result
    notified = set(prev_result.get("notified_ids", []))
    matches = []
    for listing in candidates:
        cached = cache.get(listing["id"])
        det = details_from_dict(cached) if cached else None
        score, reasons = score_listing(listing, det, profile)
        # a match needs real details with at least one area; price alone is not enough
        has_area = det is not None and det.ok and bool(det.usable_area or det.plot_area)
        is_match = score >= profile["threshold"] and has_area
        if not has_area:
            reasons = reasons + ["čeká na detail inzerátu"]
        matches.append({
            **{k: listing.get(k) for k in LISTING_KEYS},
            "score": score,
            "reasons": reasons,
            "match": is_match,
            "new": is_match and not first_run and listing["id"] not in notified,
            "details": public_details(det),
        })
    if first_run:
        # baseline every current candidate, incl. ones whose details arrive in later runs
        notified |= {m["id"] for m in matches}

    matches.sort(key=lambda m: (-m["score"], m["price"] or 0))
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "profile": {k: profile[k] for k in ("slug", "name", "threshold", "reference_urls")},
        "matches": matches,
        "new_ids": [m["id"] for m in matches if m["new"]],
        "notified_ids": sorted(notified),
    }


PRIVATE_DETAIL_FIELDS = ("agent",)  # people's names never go to the public data/site


def public_details(det: ListingDetails | None) -> dict | None:
    if det is None or not det.ok:
        return None
    d = details_to_dict(det)
    for k in PRIVATE_DETAIL_FIELDS:
        d.pop(k, None)
    return d


def mark_notified(result: dict) -> None:
    """Record that this run's new matches were delivered."""
    result["notified_ids"] = sorted(set(result.get("notified_ids", [])) | set(result["new_ids"]))


RESERVED_SLUGS = {"details_cache", "portal_health"}


def validate_profile(profile: dict, area_slugs: set[str]) -> None:
    slug = profile.get("slug", "")
    if not slug or slug in area_slugs or slug in RESERVED_SLUGS:
        raise ValueError(f"profile slug {slug!r} collides with an existing data file")


def run_profiles(max_fetch: int = 40) -> list[tuple[dict, dict]]:
    """Run every profile in config/profiles.json; persist results and the details cache."""
    from src.config import load_area_data, load_areas, load_json_data, load_profiles, save_json_data
    from src.notifications.email_sender import send_similar_email
    from src.similar.site import generate_similar_html

    area_slugs = {a["slug"] for a in load_areas()}
    cache = load_json_data("details_cache", {})
    results = []
    for profile in load_profiles():
        validate_profile(profile, area_slugs)
        area_data = load_area_data(profile["area"])
        prev = load_json_data(profile["slug"], {})
        result = asyncio.run(update_similar(area_data, profile, cache, prev, max_fetch=max_fetch))
        for entry in cache.values():  # the cache is committed too
            for k in PRIVATE_DETAIL_FIELDS:
                entry.pop(k, None)
        save_json_data("details_cache", cache)
        generate_similar_html(result)

        new = [m for m in result["matches"] if m["new"]]
        if new:
            try:
                if send_similar_email(profile["name"], profile["email_recipients"], new,
                                      f"{DASHBOARD_BASE_URL}/{profile['slug']}.html"):
                    mark_notified(result)
            except Exception as e:  # keep them "new" so the next run retries
                print(f"  {profile['slug']}: email failed - {e}")
        save_json_data(profile["slug"], result)

        matched = [m for m in result["matches"] if m["match"]]
        print(f"  {profile['slug']}: {len(result['matches'])} candidates, "
              f"{len(matched)} matches, {len(new)} new")
        results.append((profile, result))
    return results
