"""Main orchestrator: scrape → normalize → filter → dedup → diff → email → generate."""

import asyncio
import json
from datetime import datetime, timezone

from src.config import (
    load_areas, load_localities, load_aliases, load_blacklists,
    load_url_patterns, load_portal_health, save_portal_health,
    load_area_data, save_area_data,
)
from src.models import NormalizedListing
from src.pipeline.normalizer import normalize_listing
from src.pipeline.filters import FilterPipeline
from src.pipeline.dedup import deduplicate
from src.diff import diff_listings
from src.notifications.email_sender import send_report_email
from src.site_generator import generate_html
from src.scrapers import import_all_scrapers, SCRAPERS

# Import all scrapers to trigger registration
import_all_scrapers()

DASHBOARD_BASE_URL = "https://plev1n.github.io/reality-fetcher-v2"


def main():
    areas = load_areas()
    localities = load_localities()
    aliases = load_aliases()
    blacklists = load_blacklists()
    url_patterns = load_url_patterns()
    portal_health = load_portal_health()

    all_types = set()
    for area in areas:
        all_types.update(area["types"])

    # Scrape all active portals
    all_raw = {}
    for portal_name, scraper_cls in SCRAPERS.items():
        health = portal_health.get(portal_name, {})
        if not health.get("active", True):
            # Check if cooldown expired
            until = health.get("deactivated_until")
            if until and datetime.fromisoformat(until) > datetime.now(timezone.utc):
                continue
            else:
                health["active"] = True
                health["failures"] = 0

        try:
            scraper = scraper_cls()
            portal_listings = []
            for typ in all_types:
                raw = asyncio.run(scraper.scrape(typ))
                portal_listings.extend(raw)
            all_raw[portal_name] = portal_listings
            health["failures"] = 0
            print(f"  {portal_name}: {len(portal_listings)} raw listings")
        except Exception as e:
            print(f"  {portal_name}: ERROR - {e}")
            failures = health.get("failures", 0) + 1
            health["failures"] = failures
            if failures >= 3:
                health["active"] = False
                cooldown = datetime.now(timezone.utc).isoformat()
                health["deactivated_until"] = cooldown
                print(f"  {portal_name}: deactivated after {failures} failures")

    # Process per area
    for area in areas:
        print(f"\nProcessing area: {area['name']}")
        prev_data = load_area_data(area["slug"])
        area_locs = localities.get(area["slug"], [])
        loc_ids = {loc["id"] for loc in area_locs}
        blacklist = blacklists.get(area["slug"], [])
        url_pats = url_patterns.get(area["slug"], [])

        pipeline = FilterPipeline.create(
            allowed_types=area["types"],
            max_price=area["max_price"],
            min_area=area["min_area"],
            active_locality_ids=loc_ids,
            blacklist_words=blacklist,
            url_blocked_patterns=url_pats,
        )

        candidates = []
        unresolved_locations = {}
        for portal_name, raw_listings in all_raw.items():
            for raw in raw_listings:
                normalized = normalize_listing(raw, aliases, localities)
                if normalized is None:
                    loc = (raw.location_raw or "").strip()
                    if loc:
                        unresolved_locations[loc] = unresolved_locations.get(loc, 0) + 1
                    continue
                if not pipeline.apply(normalized):
                    continue
                candidates.append(normalized)

        if unresolved_locations:
            top = sorted(unresolved_locations.items(), key=lambda x: -x[1])[:30]
            print(f"  Top unresolved locations ({len(unresolved_locations)} unique):")
            for loc, count in top:
                print(f"    {count:4d}x  {loc}")

        print(f"  Candidates after filter: {len(candidates)}")

        unique = deduplicate(candidates)
        print(f"  After dedup: {len(unique)}")

        current_dicts = [l.to_dict() for l in unique]
        new, changed, removed, unchanged = diff_listings(prev_data, current_dicts)
        print(f"  New: {len(new)}, Changed: {len(changed)}, Removed: {len(removed)}, Unchanged: {len(unchanged)}")

        # Build updated data
        all_listings = new + changed + unchanged + removed
        updated_data = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "area": {"name": area["name"], "slug": area["slug"]},
            "listings": all_listings,
        }
        save_area_data(area["slug"], updated_data)

        # Generate HTML
        generate_html(area, updated_data)

        # Send email
        if new or changed or removed:
            dashboard_url = f"{DASHBOARD_BASE_URL}/{area['slug']}.html"
            send_report_email(
                area_name=area["name"],
                recipients=area["email_recipients"],
                new=new,
                changed=changed,
                removed=removed,
                dashboard_url=dashboard_url,
            )

    save_portal_health(portal_health)
    print("\nDone!")


if __name__ == "__main__":
    main()
