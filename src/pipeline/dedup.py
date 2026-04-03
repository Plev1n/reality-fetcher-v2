"""Cross-portal deduplication using 5 matching strategies."""

import re
import unicodedata
from collections import defaultdict
from src.models import NormalizedListing


PORTAL_PRIORITY: dict[str, int] = {
    "sreality": 1, "idnes": 2, "realitymix": 3, "bezrealitky": 4,
    "bazos": 5, "realingo": 6, "eurobydleni": 7, "sousede": 8,
    "remaxcz": 9, "realitycz": 10, "realcity": 11, "realhit": 12,
    "century21": 13, "moravskereality": 14, "rksting": 15,
    "boreality": 16, "realityregio": 17, "mmreality": 18,
}


def _normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip diacritics, strip non-alnum."""
    if not title:
        return ""
    t = title.lower().strip()
    t = t.replace("²", "2").replace("\u00b2", "2")
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]", "", t)
    return t


def _numeric_fingerprint(title: str) -> str:
    """Extract fingerprint of all meaningful numbers in title."""
    if not title:
        return ""
    nums = re.findall(r"\d[\d\s\xa0]*", title)
    cleaned = [n.replace(" ", "").replace("\xa0", "") for n in nums]
    meaningful = [n for n in cleaned if len(n) >= 2]
    if len(meaningful) < 2:
        return ""
    return "nums_" + "_".join(sorted(meaningful))


def _price_area_key(price: int | None, area: int | None) -> str:
    """Composite key from price + area."""
    if not price or not area or price <= 100 or area <= 0:
        return ""
    return f"pa_{int(price)}_{int(area)}"


def _price_only_key(price: int | None) -> str:
    """Key from price alone (non-round only)."""
    if not price or price <= 100:
        return ""
    p = int(price)
    if p % 1_000_000 == 0:
        return ""
    return f"price_{p}"


def _area_only_key(area: int | None) -> str:
    """Key from area alone (non-round only)."""
    if not area or area <= 0:
        return ""
    a = int(area)
    if a % 100 == 0:
        return ""
    return f"area_{a}"


def deduplicate(listings: list[NormalizedListing]) -> list[NormalizedListing]:
    """Remove cross-portal duplicates. Keep highest-priority portal version."""
    if not listings:
        return []

    # Build dedup groups: key -> list of listings
    groups: dict[str, list[NormalizedListing]] = defaultdict(list)

    for listing in listings:
        keys = set()

        # Strategy 1: Exact normalized title
        title_key = _normalize_title(listing.title)
        if title_key:
            keys.add(title_key)

        # Strategy 2: Numeric fingerprint
        num_key = _numeric_fingerprint(listing.title)
        if num_key:
            keys.add(num_key)

        # Strategy 3: Price + area
        pa_key = _price_area_key(listing.price, listing.area_m2)
        if pa_key:
            keys.add(pa_key)

        # Strategy 4: Price only
        po_key = _price_only_key(listing.price)
        if po_key:
            keys.add(po_key)

        # Strategy 5: Area only
        ao_key = _area_only_key(listing.area_m2)
        if ao_key:
            keys.add(ao_key)

        for key in keys:
            groups[key].append(listing)

    # Find all listings that are duplicates of each other
    # Use union-find to group connected listings
    listing_key = lambda l: f"{l.portal}_{l.portal_id}"
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    listing_map: dict[str, NormalizedListing] = {}
    for listing in listings:
        lk = listing_key(listing)
        listing_map[lk] = listing
        parent[lk] = lk

    for group in groups.values():
        if len(group) < 2:
            continue
        first_key = listing_key(group[0])
        for other in group[1:]:
            union(first_key, listing_key(other))

    # Group by root and pick highest priority from each group
    root_groups: dict[str, list[NormalizedListing]] = defaultdict(list)
    for listing in listings:
        root = find(listing_key(listing))
        root_groups[root].append(listing)

    result = []
    for group in root_groups.values():
        group.sort(key=lambda l: (PORTAL_PRIORITY.get(l.portal, 99), l.portal_id))
        result.append(group[0])

    return result
