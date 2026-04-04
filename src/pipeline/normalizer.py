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
# Also match bare "m" preceded by digits and whitespace (e.g., "393 m,")
_AREA_PATTERN_BARE_M = re.compile(r"(\d[\d\s,.]*)\s*m(?:\s|,|$)")
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


def _parse_area_number(raw_num: str) -> int | None:
    """Parse a raw number string to int, handling Czech formatting.

    Handles: "1 058", "7.540", "1,058", "7 540,5", "393"
    Czech convention: dot and space are thousands separators, comma is decimal.
    """
    s = raw_num.replace("\xa0", " ").strip()

    # If contains dot as thousands separator (e.g., "7.540") — no decimal digits after dot > 2
    # Czech: "7.540" = 7540, but "7.5" could be ambiguous
    if "." in s:
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            # Thousands separator: "7.540" -> "7540"
            s = s.replace(".", "")
        else:
            # Decimal point, take integer part
            s = parts[0]

    # Strip comma (either thousands sep or decimal)
    if "," in s:
        parts = s.split(",")
        # "1,058" with 3 digits after = thousands, "540,5" = decimal
        if len(parts) == 2 and len(parts[1]) == 3:
            s = s.replace(",", "")
        else:
            s = parts[0]  # Take integer part

    s = s.replace(" ", "").strip()
    if s.isdigit() and int(s) > 0:
        return int(s)
    return None


def normalize_area(area_raw: str | None) -> tuple[int | None, bool]:
    """Parse raw area to (area_m2, is_unknown).

    FIXED: v1 bug concatenated room count with area ('3+1 65 m2' -> 165).
    v2 strips room patterns first, then extracts last m2 match.
    Also handles Czech number formatting (dot/space as thousands separator).
    """
    if not area_raw or not area_raw.strip():
        return None, True

    text = area_raw.strip()

    # Strip room patterns: "3+1", "2+kk", "1+KK" etc.
    text = _ROOM_PATTERN.sub("", text)

    # Find all m²/m2 matches, take the last one (e.g., "dum 89 m², pozemek 544 m²" -> 544)
    matches = _AREA_PATTERN.findall(text)
    if matches:
        value = _parse_area_number(matches[-1])
        if value:
            return value, False

    # Try bare "m" pattern (e.g., "393 m," or "1032 m")
    matches_bare = _AREA_PATTERN_BARE_M.findall(text)
    if matches_bare:
        value = _parse_area_number(matches_bare[-1])
        if value:
            return value, False

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
    # Normalize various dash characters to standard hyphen
    raw = raw.replace("\u2013", "-").replace("\u2014", "-").replace("\u2010", "-")

    # Helper to try alias match
    def _try_alias(name: str):
        name_lower = name.lower()
        for alias, loc_id in aliases.items():
            if alias.lower() == name_lower:
                loc = loc_lookup.get(loc_id)
                if loc:
                    coords = tuple(loc["coordinates"]) if loc.get("coordinates") else None
                    return loc_id, loc["name"], coords
        return None

    # 1. Exact alias match (case-insensitive)
    result = _try_alias(raw)
    if result:
        return result

    # 2. Strip postal code (Bazos formats: "Ostrava708 00", "Frýdek - Místek738 01", "Třinec, 739 61")
    stripped = re.sub(r",?\s*\d{3}\s*\d{2}\s*$", "", raw).strip()
    # Also handle PSČ glued to name without space
    stripped = re.sub(r"\d{3}\s*\d{2}\s*$", "", stripped).strip()
    if stripped != raw:
        result = _try_alias(stripped)
        if result:
            return result

    # 3. Strip district suffix ("okres Frydek-Mistek")
    without_district = re.sub(r",?\s*(okres|okr\.?)\s+.*$", "", stripped, flags=re.IGNORECASE).strip()
    without_district = without_district.split(",")[0].strip()
    if without_district and without_district != stripped:
        result = _try_alias(without_district)
        if result:
            return result

    # 4. Substring match on aliases
    target = (without_district or stripped).lower()
    for alias, loc_id in aliases.items():
        if alias.lower() in target:
            loc = loc_lookup.get(loc_id)
            if loc:
                coords = tuple(loc["coordinates"]) if loc.get("coordinates") else None
                return loc_id, loc["name"], coords

    # 5. Extract base municipality (before " - " or " / ")
    for sep in [" - ", " / "]:
        municipality = target.split(sep)[0].strip()
        if municipality and municipality != target:
            result = _try_alias(municipality)
            if result:
                return result

    return None


def _parse_all_areas(text: str) -> list[int]:
    """Extract all area values from text, in order. Used to get both house area and plot area."""
    if not text:
        return []
    text = _ROOM_PATTERN.sub("", text)
    results = []
    for match in _AREA_PATTERN.findall(text):
        val = _parse_area_number(match)
        if val:
            results.append(val)
    if not results:
        for match in _AREA_PATTERN_BARE_M.findall(text):
            val = _parse_area_number(match)
            if val:
                results.append(val)
    return results


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

    # Parse areas: for houses, title often has "domu 120 m², pozemek 1180 m²"
    # First = usable area (house), Last = plot area
    # For land (pozemek), there's typically just one area = plot
    all_areas = _parse_all_areas(raw.area_raw or raw.title)

    if all_areas:
        if typ == "dum" and len(all_areas) >= 2:
            # House: first = usable area, last = plot area
            usable_area = all_areas[0]
            plot_area = all_areas[-1]
            area = plot_area          # For filtering (min 750m² = plot)
            area_for_price = usable_area  # For price/m² calculation
        else:
            # Land or single area: use the last (largest) value
            area = all_areas[-1]
            area_for_price = area
        area_unknown = False
    else:
        area, area_for_price, area_unknown = None, None, True

    location_result = resolve_location(raw.location_raw or "", aliases, localities)
    if location_result is None:
        return None

    loc_id, loc_name, loc_coords = location_result

    # Use listing coordinates if available, fall back to locality center
    coordinates = raw.coordinates or loc_coords

    price_per_m2 = None
    if price and area_for_price and area_for_price > 0:
        price_per_m2 = round(price / area_for_price)

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
