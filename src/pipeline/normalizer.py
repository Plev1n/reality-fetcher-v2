"""Normalize raw listing data into canonical form."""

import re
import unicodedata
from src.models import RawListing, NormalizedListing


# --- Type mapping ---

_TYPE_MAP: dict[str, str] = {
    # Houses
    "rodinné domy": "dum", "rodinný dům": "dum", "rodinny dum": "dum",
    "domy": "dum", "dům": "dum", "dum": "dum", "vila": "dum",
    "rodinne domy": "dum", "rd": "dum",
    "house_family": "dum", "rodinný": "dum",
    # Land
    "pozemky": "pozemek", "pozemek": "pozemek", "stavební pozemek": "pozemek",
    "stavebni pozemek": "pozemek", "stavební parcela": "pozemek",
    "land_residential": "pozemek", "stavební parcely": "pozemek",
    # Apartments
    "byty": "byt", "byt": "byt", "apartment": "byt",
    "1+kk": "byt", "1+1": "byt", "2+kk": "byt", "2+1": "byt",
    "3+kk": "byt", "3+1": "byt", "4+kk": "byt", "4+1": "byt",
}

_URL_TYPE_PATTERNS: list[tuple[str, str]] = [
    ("/pozemk", "pozemek"), ("/land", "pozemek"),
    ("/dom", "dum"), ("/house", "dum"), ("/vil", "dum"), ("/rodinne-dom", "dum"),
    ("/byt", "byt"), ("/apartment", "byt"), ("/flat", "byt"),
]

_PRICE_UNKNOWN_PATTERNS = [
    "na vyžádání", "na vyzadani", "cena na vyžádání", "cena na vyzadani",
    "info o ceně", "info o cene", "dohodou", "na dotaz", "dle dohody",
]

_ROOM_PATTERN = re.compile(r"\d\+(?:\d|kk|KK)")
_AREA_PATTERN = re.compile(r"(\d[\d\s,.]*)\s*m[²2\u00b2]")
_NUMERIC_RE = re.compile(r"[\d]+")


def strip_diacritics(text: str) -> str:
    """Remove diacritics from text (e->e, s->s, etc.)."""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalize_type(type_raw: str | None, url: str) -> str | None:
    """Normalize raw type to dum/pozemek/byt. URL overrides portal label."""
    url_lower = url.lower()
    # Check URL first — more reliable than portal labels
    for pattern, canonical in _URL_TYPE_PATTERNS:
        if pattern in url_lower:
            url_type = canonical
            break
    else:
        url_type = None

    if type_raw:
        key = type_raw.strip().lower()
        if key in _TYPE_MAP:
            raw_type = _TYPE_MAP[key]
        else:
            # Fuzzy match
            raw_type = None
            for pattern, canonical in _TYPE_MAP.items():
                if pattern in key or key in pattern:
                    raw_type = canonical
                    break
            # If URL says pozemek but portal says dum, trust URL
        if url_type and raw_type and url_type != raw_type:
            return url_type
        if raw_type:
            return raw_type

    return url_type


def normalize_price(price_raw: str | None) -> tuple[int | None, bool]:
    """Parse raw price to (price_czk, is_unknown)."""
    if price_raw is None:
        return None, True

    cleaned = price_raw.strip().lower()

    for pattern in _PRICE_UNKNOWN_PATTERNS:
        if pattern in cleaned:
            return None, True

    # Strip currency
    cleaned = cleaned.replace("kč", "").replace("kc", "").replace("czk", "")
    cleaned = cleaned.replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", "").strip()

    match = _NUMERIC_RE.search(cleaned)
    if match:
        try:
            value = int(match.group())
            if value <= 1:
                return None, True  # Symbolic 1 Kc = unknown
            return value, False
        except ValueError:
            pass

    return None, True


def normalize_area(area_raw: str | None) -> tuple[int | None, bool]:
    """Parse raw area to (area_m2, is_unknown).

    FIXED: v1 bug concatenated room count with area ('3+1 65 m2' -> 165).
    v2 strips room patterns first, then extracts last m2 match.
    """
    if not area_raw or not area_raw.strip():
        return None, True

    text = area_raw.strip()

    # Strip room patterns: "3+1", "2+kk", "1+KK" etc.
    text = _ROOM_PATTERN.sub("", text)

    # Find all m2 matches, take the last one (e.g., "dum 89 m2, pozemek 544 m2" -> 544)
    matches = _AREA_PATTERN.findall(text)
    if matches:
        last = matches[-1].replace(" ", "").replace("\xa0", "").replace(",", "").replace(".", "")
        try:
            value = int(last)
            if value > 0:
                return value, False
        except ValueError:
            pass

    # Fallback: try to find any number before "m" in cleaned text
    cleaned = text.replace("m²", "").replace("m2", "").replace("m\u00b2", "")
    cleaned = cleaned.replace("\xa0", "").replace(" ", "").strip()
    match = _NUMERIC_RE.search(cleaned)
    if match:
        try:
            value = int(match.group())
            if value > 0:
                return value, False
        except ValueError:
            pass

    return None, True


def resolve_location(
    raw_name: str,
    aliases: dict[str, str],
    localities: dict[str, list[dict]],
) -> tuple[str, str, tuple[float, float] | None] | None:
    """Resolve raw location to (location_id, canonical_name, coordinates) or None.

    Resolution order:
    1. Exact alias match (case-insensitive)
    2. Strip postal code, strip district suffix, try again
    3. Substring match on aliases
    4. Extract base municipality and try
    """
    if not raw_name or not raw_name.strip():
        return None

    # Build lookup: location_id -> {name, coordinates}
    loc_lookup: dict[str, dict] = {}
    for area_locs in localities.values():
        for loc in area_locs:
            loc_lookup[loc["id"]] = loc

    raw = raw_name.strip()

    # 1. Exact alias match (case-insensitive)
    for alias, loc_id in aliases.items():
        if alias.lower() == raw.lower():
            loc = loc_lookup.get(loc_id)
            if loc:
                coords = tuple(loc["coordinates"]) if loc.get("coordinates") else None
                return loc_id, loc["name"], coords

    # 2. Strip postal code from end (Bazos: "Ostrava708 00")
    stripped = re.sub(r"\s*\d{3}\s*\d{2}\s*$", "", raw).strip()
    if stripped != raw:
        for alias, loc_id in aliases.items():
            if alias.lower() == stripped.lower():
                loc = loc_lookup.get(loc_id)
                if loc:
                    coords = tuple(loc["coordinates"]) if loc.get("coordinates") else None
                    return loc_id, loc["name"], coords

    # 3. Strip district suffix ("okres Frydek-Mistek")
    without_district = re.sub(r",?\s*(okres|okr\.?)\s+.*$", "", stripped, flags=re.IGNORECASE).strip()
    without_district = without_district.split(",")[0].strip()
    if without_district and without_district != stripped:
        for alias, loc_id in aliases.items():
            if alias.lower() == without_district.lower():
                loc = loc_lookup.get(loc_id)
                if loc:
                    coords = tuple(loc["coordinates"]) if loc.get("coordinates") else None
                    return loc_id, loc["name"], coords

    # 4. Substring match on aliases
    target = (without_district or stripped).lower()
    for alias, loc_id in aliases.items():
        if alias.lower() in target:
            loc = loc_lookup.get(loc_id)
            if loc:
                coords = tuple(loc["coordinates"]) if loc.get("coordinates") else None
                return loc_id, loc["name"], coords

    # 5. Extract base municipality (before " - ")
    municipality = target.split(" - ")[0].strip()
    if municipality and municipality != target:
        for alias, loc_id in aliases.items():
            if alias.lower() == municipality:
                loc = loc_lookup.get(loc_id)
                if loc:
                    coords = tuple(loc["coordinates"]) if loc.get("coordinates") else None
                    return loc_id, loc["name"], coords

    return None


def normalize_listing(
    raw: RawListing,
    aliases: dict[str, str],
    localities: dict[str, list[dict]],
) -> NormalizedListing | None:
    """Full normalization pipeline: raw -> normalized. Returns None if location can't be resolved."""
    typ = normalize_type(raw.type_raw, raw.url)
    if not typ:
        return None

    price, price_unknown = normalize_price(raw.price_raw)
    area, area_unknown = normalize_area(raw.area_raw)

    location_result = resolve_location(raw.location_raw or "", aliases, localities)
    if location_result is None:
        return None

    loc_id, loc_name, loc_coords = location_result

    # Use listing coordinates if available, fall back to locality center
    coordinates = raw.coordinates or loc_coords

    price_per_m2 = None
    if price and area and area > 0:
        price_per_m2 = round(price / area)

    return NormalizedListing(
        portal=raw.portal,
        portal_id=raw.portal_id,
        title=raw.title,
        url=raw.url,
        type=typ,
        price=price,
        price_unknown=price_unknown,
        area_m2=area,
        area_unknown=area_unknown,
        price_per_m2=price_per_m2,
        location=loc_name,
        location_id=loc_id,
        coordinates=coordinates,
    )
