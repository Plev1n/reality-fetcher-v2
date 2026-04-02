# Reality Fetcher v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete real estate monitoring system that scrapes 18 Czech portals, filters/deduplicates listings, serves a static dashboard on GitHub Pages, and sends email notifications via Gmail.

**Architecture:** GitHub Actions runs Python scrapers on cron (2x daily) → normalizes, filters, deduplicates → diffs against previous JSON data files → generates static HTML dashboards → sends Gmail notifications for changes → commits updated data + HTML to repo → GitHub Pages serves the dashboard.

**Tech Stack:** Python 3.12, httpx, selectolax, vanilla HTML/CSS/JS, GitHub Actions, Gmail SMTP

**Spec:** `specs.md` in project root

---

## Phase 1: Config + Models + Core Pipeline

Foundation that everything depends on. Fully testable without scraping.

---

### Task 1: Project setup + config files

**Files:**
- Create: `requirements.txt`
- Create: `config/areas.json`
- Create: `config/localities.json`
- Create: `config/aliases.json`
- Create: `config/blacklist.json`
- Create: `config/url_patterns.json`
- Create: `data/portal_health.json`
- Create: `data/fm.json`
- Create: `data/poruba.json`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
httpx>=0.27
selectolax>=0.3
pytest>=8.0
```

- [ ] **Step 2: Create config/areas.json**

```json
[
  {
    "slug": "fm",
    "name": "Frýdek-Místek",
    "types": ["dum", "pozemek"],
    "max_price": 10000000,
    "min_area": 750,
    "email_recipients": ["dav.plev@seznam.cz"]
  },
  {
    "slug": "poruba",
    "name": "Ostrava-Poruba",
    "types": ["byt"],
    "max_price": 4000000,
    "min_area": 20,
    "email_recipients": ["ivos.pleva@gmail.com"]
  }
]
```

- [ ] **Step 3: Create config/localities.json**

Full file with all 29 FM municipalities + 1 Poruba. See specs.md Section 11.2 for complete content. Copy it exactly.

- [ ] **Step 4: Create config/aliases.json**

Full alias mapping from specs.md Section 11.3. All 49 entries. Copy exactly.

- [ ] **Step 5: Create config/blacklist.json**

```json
{
  "fm": [
    "les", "lesni", "zemedelsky", "zemedelska", "zemědělská", "zemedelska puda",
    "orna puda", "pole", "louka", "louky", "chata", "chalupa", "rekreacni",
    "zahrada", "zahradkarska kolonie", "komercni", "komerční", "komercni vystavba",
    "komerční výstavba", "komerční pozemek", "prumyslovy", "garaz", "pasport",
    "provozni", "provozní", "mobilni dum", "mobilní dům", "vinice", "byt", "bytu",
    "ordinace", "kancelar", "kancelář", "pronajem", "pronájem",
    "rezervovano", "rezervováno",
    "bila", "bílá", "bukovec", "bystrice", "bystřice", "dobratice", "domaslavice",
    "dolni domaslavice", "dolní domaslavice", "horni domaslavice", "horní domaslavice",
    "frycovice", "fryčovice", "hnojnik", "hnojník", "hradek", "hrádek", "hukvaldy",
    "jablunkov", "komorni lhotka", "komorní lhotka", "krasna", "krásná", "krmelín",
    "lucina", "lučina", "milikov", "milíkov", "moravka", "morávka",
    "mosty u jablunkova", "mosty u jabl", "navsi", "návší", "nosovice",
    "nydek", "nýdek", "pazderna", "pazderná", "pisek", "písek", "prazmo",
    "reka", "řeka", "ropice", "sobesovice", "soběšovice", "stare hamry", "staré hamry",
    "stritez", "střítež", "tranovice", "třanovice", "trinec", "třinec",
    "trojanovice", "vendryne", "vendryně", "vojkovice",
    "vysni lhoty", "vyšní lhoty", "lomna", "lomná",
    "horni tosanovice", "horní tošanovice"
  ],
  "poruba": [
    "pronájem", "pronajem", "podnájem", "podnajem",
    "rezervováno", "rezervovano", "prodáno", "prodano",
    "komercni", "komerční", "kancelář", "kancelar", "ordinace", "provozní", "provozni",
    "garáž", "garaz", "garážové stání", "garazove stani", "parking",
    "sklep", "skladový", "skladovy",
    "dražba", "drazba", "aukce",
    "poptávka", "poptavka", "hledám", "hledam", "koupím", "koupim", "sháním", "shanim",
    "spoluvlastnický podíl", "spoluvlastnicky podil", "podíl na bytové", "podil na bytove",
    "1/2 podíl", "1/3 podíl", "1/4 podíl", "1/8 podíl",
    "výměna bytu", "vymena bytu", "výměnou", "vymenou", "vyměním", "vymenim",
    "nabídněte", "nabidnete"
  ]
}
```

- [ ] **Step 6: Create config/url_patterns.json**

```json
{
  "fm": [
    "vodni-ploch", "rybnik", "louka", "les", "zahrady", "zemedelsk",
    "orna-puda", "ostatni-ostatni", "ostatni-pozemky", "prumyslovy",
    "areal", "komercni", "apartma", "na-klic", "rekreacni",
    "ostrava-hrabova", "kuncice-pod-ondrej", "oldrichovic", "brusperk", "trinec"
  ],
  "poruba": []
}
```

- [ ] **Step 7: Create initial data files**

`data/fm.json`:
```json
{"generated": null, "area": {"name": "Frýdek-Místek", "slug": "fm"}, "listings": []}
```

`data/poruba.json`:
```json
{"generated": null, "area": {"name": "Ostrava-Poruba", "slug": "poruba"}, "listings": []}
```

`data/portal_health.json`: Full file from specs.md Section 11.6 — all 18 portals set to active with 0 failures.

- [ ] **Step 8: Create src/__init__.py and tests/__init__.py**

Both empty files.

- [ ] **Step 9: Create src/config.py**

```python
"""Load JSON configuration files."""

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR = Path(__file__).parent.parent / "data"


def load_areas() -> list[dict]:
    return json.loads((CONFIG_DIR / "areas.json").read_text())


def load_localities() -> dict[str, list[dict]]:
    return json.loads((CONFIG_DIR / "localities.json").read_text())


def load_aliases() -> dict[str, str]:
    return json.loads((CONFIG_DIR / "aliases.json").read_text())


def load_blacklists() -> dict[str, list[str]]:
    return json.loads((CONFIG_DIR / "blacklist.json").read_text())


def load_url_patterns() -> dict[str, list[str]]:
    return json.loads((CONFIG_DIR / "url_patterns.json").read_text())


def load_portal_health() -> dict:
    return json.loads((DATA_DIR / "portal_health.json").read_text())


def save_portal_health(health: dict) -> None:
    (DATA_DIR / "portal_health.json").write_text(
        json.dumps(health, indent=2, ensure_ascii=False) + "\n"
    )


def load_area_data(slug: str) -> dict:
    path = DATA_DIR / f"{slug}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"generated": None, "area": {"slug": slug}, "listings": []}


def save_area_data(slug: str, data: dict) -> None:
    (DATA_DIR / f"{slug}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    )
```

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: project setup with config files and data structures"
```

---

### Task 2: Data models

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write test for models**

```python
# tests/test_models.py
from src.models import RawListing, NormalizedListing


def test_raw_listing_creation():
    raw = RawListing(
        portal="sreality",
        portal_id="12345",
        title="Stavební pozemek 2,473 m²",
        url="https://sreality.cz/detail/12345",
        type_raw="Pozemky",
        price_raw="7 980 000 Kč",
        area_raw="2 473 m²",
        location_raw="Frýdlant nad Ostravicí",
    )
    assert raw.portal == "sreality"
    assert raw.images == []
    assert raw.coordinates is None


def test_normalized_listing_price_per_m2():
    listing = NormalizedListing(
        portal="sreality",
        portal_id="12345",
        title="Stavební pozemek",
        url="https://sreality.cz/detail/12345",
        type="pozemek",
        price=7980000,
        price_unknown=False,
        area_m2=2473,
        area_unknown=False,
        price_per_m2=3227,
        location="Frýdlant nad Ostravicí",
        location_id="frydlant",
        coordinates=(49.527, 18.359),
    )
    assert listing.price_per_m2 == 3227


def test_normalized_listing_to_dict():
    listing = NormalizedListing(
        portal="sreality",
        portal_id="12345",
        title="Test",
        url="https://example.com",
        type="dum",
        price=5000000,
        price_unknown=False,
        area_m2=1000,
        area_unknown=False,
        price_per_m2=5000,
        location="Baška",
        location_id="baska",
        coordinates=(49.64, 18.35),
    )
    d = listing.to_dict()
    assert d["id"] == "sreality_12345"
    assert d["status"] == "active"
    assert d["price_history"] == [{"date": d["added"], "price": 5000000}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_models.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement models**

```python
# src/models.py
"""Data models for reality-fetcher v2."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawListing:
    """Raw listing data from a portal, before normalization."""
    portal: str
    portal_id: str
    title: str
    url: str
    type_raw: str | None = None
    price_raw: str | None = None
    area_raw: str | None = None
    location_raw: str | None = None
    address_raw: str | None = None
    description: str | None = None
    coordinates: tuple[float, float] | None = None
    images: list[str] = field(default_factory=list)


@dataclass
class NormalizedListing:
    """Normalized listing ready for storage and display."""
    portal: str
    portal_id: str
    title: str
    url: str
    type: str                              # "dum" | "pozemek" | "byt"
    price: int | None
    price_unknown: bool
    area_m2: int | None
    area_unknown: bool
    price_per_m2: int | None
    location: str                          # Canonical locality name
    location_id: str                       # Locality ID for filtering
    coordinates: tuple[float, float] | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict for data file storage."""
        today = date.today().isoformat()
        return {
            "id": f"{self.portal}_{self.portal_id}",
            "status": "active",
            "type": self.type,
            "title": self.title,
            "location": self.location,
            "location_id": self.location_id,
            "coordinates": list(self.coordinates) if self.coordinates else None,
            "area_m2": self.area_m2,
            "price": self.price,
            "price_per_m2": self.price_per_m2,
            "price_unknown": self.price_unknown,
            "area_unknown": self.area_unknown,
            "url": self.url,
            "portal": self.portal,
            "added": today,
            "updated": today,
            "price_history": [{"date": today, "price": self.price}] if self.price else [],
            "removed_date": None,
        }
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_models.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add RawListing and NormalizedListing data models"
```

---

### Task 3: Normalizer (with area parsing fix)

**Files:**
- Create: `src/pipeline/__init__.py`
- Create: `src/pipeline/normalizer.py`
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: Write failing tests for normalizer**

```python
# tests/test_normalizer.py
"""Tests for normalization functions — especially the v1 area parsing bug fix."""

from src.pipeline.normalizer import (
    normalize_type,
    normalize_price,
    normalize_area,
    resolve_location,
    normalize_listing,
    strip_diacritics,
)
from src.models import RawListing


# --- Type normalization ---

def test_type_from_raw():
    assert normalize_type("Rodinné domy", "") == "dum"
    assert normalize_type("Pozemky", "") == "pozemek"
    assert normalize_type("Byty", "") == "byt"
    assert normalize_type("Rodinný dům", "") == "dum"
    assert normalize_type("Stavební pozemek", "") == "pozemek"
    assert normalize_type("Byt", "") == "byt"


def test_type_from_url_fallback():
    assert normalize_type("Unknown", "/prodej/domy/detail") == "dum"
    assert normalize_type("Unknown", "/prodej/pozemky/detail") == "pozemek"
    assert normalize_type("Unknown", "/prodej/byty/detail") == "byt"
    assert normalize_type("Unknown", "/nemovitosti/prodej/domy/") == "dum"


def test_type_remax_land_misclassification():
    """RE/MAX labels land as Dům — URL should override."""
    assert normalize_type("Dům", "/reality/pozemky/prodej/moravskoslezsky-kraj/detail") == "pozemek"


# --- Price normalization ---

def test_price_normal():
    assert normalize_price("7 980 000 Kč") == (7980000, False)
    assert normalize_price("3,840,000 CZK") == (3840000, False)
    assert normalize_price("2560000") == (2560000, False)


def test_price_unknown():
    assert normalize_price("Cena na vyžádání") == (None, True)
    assert normalize_price("Na vyžádání") == (None, True)
    assert normalize_price("Info o ceně u RK") == (None, True)
    assert normalize_price(None) == (None, True)
    assert normalize_price("dohodou") == (None, True)


def test_price_one_czk():
    """Symbolic 1 Kč prices should be treated as unknown."""
    assert normalize_price("1 Kč") == (None, True)


# --- Area normalization (THE BIG FIX) ---

def test_area_normal():
    assert normalize_area("2 473 m²") == (2473, False)
    assert normalize_area("800 m2") == (800, False)
    assert normalize_area("1 200m²") == (1200, False)


def test_area_room_count_not_concatenated():
    """v1 bug: '3+1 65 m²' was parsed as 165 m². Must be 65."""
    assert normalize_area("3+1 65 m²") == (65, False)
    assert normalize_area("2+1 51 m²") == (51, False)
    assert normalize_area("1+1 38m2") == (38, False)
    assert normalize_area("2+kk 45 m²") == (45, False)
    assert normalize_area("1+KK 22 m2") == (22, False)


def test_area_multiple_values_takes_last():
    """'dum 89 m², pozemek 544 m²' should return 544 (last)."""
    assert normalize_area("dum 89 m², pozemek 544 m²") == (544, False)


def test_area_unknown():
    assert normalize_area(None) == (None, True)
    assert normalize_area("") == (None, True)
    assert normalize_area("N/A") == (None, True)


# --- Location resolution ---

def test_resolve_location_exact():
    aliases = {"Baška": "baska", "Ostrava-Poruba": "poruba"}
    localities = {"fm": [{"id": "baska", "name": "Baška", "coordinates": [49.64, 18.35]}]}
    assert resolve_location("Baška", aliases, localities) == ("baska", "Baška", (49.64, 18.35))


def test_resolve_location_alias():
    aliases = {"Baska u Frydku-Mistku": "baska"}
    localities = {"fm": [{"id": "baska", "name": "Baška", "coordinates": [49.64, 18.35]}]}
    assert resolve_location("Baska u Frydku-Mistku", aliases, localities) == ("baska", "Baška", (49.64, 18.35))


def test_resolve_location_with_district_suffix():
    aliases = {"Frýdek-Místek": "frydek_mistek"}
    localities = {"fm": [{"id": "frydek_mistek", "name": "Frýdek-Místek", "coordinates": [49.68, 18.34]}]}
    assert resolve_location("Frýdek-Místek, okres Frýdek-Místek", aliases, localities) == (
        "frydek_mistek", "Frýdek-Místek", (49.68, 18.34)
    )


def test_resolve_location_unknown():
    aliases = {}
    localities = {"fm": []}
    assert resolve_location("Neznámá obec", aliases, localities) is None


# --- Strip diacritics ---

def test_strip_diacritics():
    assert strip_diacritics("Frýdek-Místek") == "Frydek-Mistek"
    assert strip_diacritics("Třinec") == "Trinec"
    assert strip_diacritics("Čeladná") == "Celadna"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_normalizer.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement normalizer**

Create `src/pipeline/__init__.py` (empty).

```python
# src/pipeline/normalizer.py
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
    """Remove diacritics from text (ě→e, š→s, etc.)."""
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
                return None, True  # Symbolic 1 Kč = unknown
            return value, False
        except ValueError:
            pass

    return None, True


def normalize_area(area_raw: str | None) -> tuple[int | None, bool]:
    """Parse raw area to (area_m2, is_unknown).

    FIXED: v1 bug concatenated room count with area ('3+1 65 m²' → 165).
    v2 strips room patterns first, then extracts last m² match.
    """
    if not area_raw or not area_raw.strip():
        return None, True

    text = area_raw.strip()

    # Strip room patterns: "3+1", "2+kk", "1+KK" etc.
    text = _ROOM_PATTERN.sub("", text)

    # Find all m² matches, take the last one (e.g., "dum 89 m², pozemek 544 m²" → 544)
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

    # Build lookup: location_id → {name, coordinates}
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

    # 3. Strip district suffix ("okres Frýdek-Místek")
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
    """Full normalization pipeline: raw → normalized. Returns None if location can't be resolved."""
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
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_normalizer.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/ tests/test_normalizer.py
git commit -m "feat: add normalizer with area parsing bug fix"
```

---

### Task 4: Filters

**Files:**
- Create: `src/pipeline/filters.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_filters.py
from src.pipeline.filters import (
    TypeFilter, URLPatternFilter, PriceFilter, AreaFilter,
    LocationFilter, BlacklistFilter, FilterPipeline,
)
from src.models import NormalizedListing


def _make_listing(**overrides) -> NormalizedListing:
    defaults = dict(
        portal="sreality", portal_id="1", title="Test", url="https://example.com",
        type="pozemek", price=5000000, price_unknown=False,
        area_m2=1000, area_unknown=False, price_per_m2=5000,
        location="Baška", location_id="baska", coordinates=None,
    )
    defaults.update(overrides)
    return NormalizedListing(**defaults)


def test_type_filter_pass():
    f = TypeFilter(["dum", "pozemek"])
    assert f.check(_make_listing(type="pozemek")).passed is True


def test_type_filter_reject():
    f = TypeFilter(["dum", "pozemek"])
    assert f.check(_make_listing(type="byt")).passed is False


def test_price_filter_pass():
    f = PriceFilter(max_price=10000000)
    assert f.check(_make_listing(price=5000000)).passed is True


def test_price_filter_reject():
    f = PriceFilter(max_price=10000000)
    assert f.check(_make_listing(price=15000000)).passed is False


def test_price_filter_unknown_passes():
    f = PriceFilter(max_price=10000000)
    assert f.check(_make_listing(price=None, price_unknown=True)).passed is True


def test_area_filter_pass():
    f = AreaFilter(min_area=750)
    assert f.check(_make_listing(area_m2=1000)).passed is True


def test_area_filter_reject():
    f = AreaFilter(min_area=750)
    assert f.check(_make_listing(area_m2=500)).passed is False


def test_area_filter_unknown_passes():
    f = AreaFilter(min_area=750)
    assert f.check(_make_listing(area_m2=None, area_unknown=True)).passed is True


def test_location_filter_pass():
    f = LocationFilter({"baska", "frydek_mistek"})
    assert f.check(_make_listing(location_id="baska")).passed is True


def test_location_filter_reject():
    f = LocationFilter({"baska", "frydek_mistek"})
    assert f.check(_make_listing(location_id="trinec")).passed is False


def test_blacklist_filter_pass():
    f = BlacklistFilter(["pronájem", "les", "trinec"])
    assert f.check(_make_listing(title="Stavební pozemek Baška")).passed is True


def test_blacklist_filter_reject():
    f = BlacklistFilter(["pronájem", "les", "trinec"])
    assert f.check(_make_listing(title="Pronájem domu Baška")).passed is False


def test_blacklist_filter_diacritics_insensitive():
    f = BlacklistFilter(["třinec"])
    assert f.check(_make_listing(title="Pozemek Trinec")).passed is False


def test_url_pattern_filter_pass():
    f = URLPatternFilter(["zemedelsk", "komercni"])
    assert f.check(_make_listing(url="https://sreality.cz/prodej/pozemky/")).passed is True


def test_url_pattern_filter_reject():
    f = URLPatternFilter(["zemedelsk", "komercni"])
    assert f.check(_make_listing(url="https://sreality.cz/prodej/komercni-pozemky/")).passed is False


def test_pipeline_applies_all():
    pipeline = FilterPipeline.create(
        allowed_types=["pozemek"],
        max_price=10000000,
        min_area=750,
        active_locality_ids={"baska"},
        blacklist_words=["les"],
        url_blocked_patterns=["komercni"],
    )
    # Good listing passes
    assert pipeline.apply(_make_listing()) is True
    # Wrong type fails
    assert pipeline.apply(_make_listing(type="byt")) is False
    # Over price fails
    assert pipeline.apply(_make_listing(price=15000000)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_filters.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement filters**

```python
# src/pipeline/filters.py
"""Filter pipeline for rejecting irrelevant listings."""

import unicodedata
from dataclasses import dataclass
from abc import ABC, abstractmethod
from src.models import NormalizedListing


@dataclass
class FilterResult:
    passed: bool
    reason: str = ""


class BaseFilter(ABC):
    @abstractmethod
    def check(self, listing: NormalizedListing) -> FilterResult: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class TypeFilter(BaseFilter):
    def __init__(self, allowed_types: list[str]) -> None:
        self._allowed = set(allowed_types)

    @property
    def name(self) -> str:
        return "TypeFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.type in self._allowed:
            return FilterResult(passed=True)
        return FilterResult(passed=False, reason=f"Type '{listing.type}' not in {self._allowed}")


class PriceFilter(BaseFilter):
    def __init__(self, max_price: int) -> None:
        self._max = max_price

    @property
    def name(self) -> str:
        return "PriceFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.price_unknown or listing.price is None:
            return FilterResult(passed=True)
        if listing.price > self._max:
            return FilterResult(passed=False, reason=f"Price {listing.price} > max {self._max}")
        return FilterResult(passed=True)


class AreaFilter(BaseFilter):
    def __init__(self, min_area: int) -> None:
        self._min = min_area

    @property
    def name(self) -> str:
        return "AreaFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.area_unknown or listing.area_m2 is None:
            return FilterResult(passed=True)
        if listing.area_m2 < self._min:
            return FilterResult(passed=False, reason=f"Area {listing.area_m2} < min {self._min}")
        return FilterResult(passed=True)


class LocationFilter(BaseFilter):
    def __init__(self, active_ids: set[str]) -> None:
        self._active = active_ids

    @property
    def name(self) -> str:
        return "LocationFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        if listing.location_id in self._active:
            return FilterResult(passed=True)
        return FilterResult(passed=False, reason=f"Location '{listing.location_id}' not in whitelist")


class BlacklistFilter(BaseFilter):
    def __init__(self, words: list[str]) -> None:
        self._words = words

    @property
    def name(self) -> str:
        return "BlacklistFilter"

    def _strip_diacritics(self, text: str) -> str:
        nfkd = unicodedata.normalize("NFD", text)
        return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")

    def check(self, listing: NormalizedListing) -> FilterResult:
        text = f"{listing.title} {listing.url}".lower()
        text_ascii = self._strip_diacritics(text)
        for word in self._words:
            word_lower = word.lower()
            word_ascii = self._strip_diacritics(word_lower)
            if word_lower in text or word_ascii in text_ascii:
                return FilterResult(passed=False, reason=f"Blacklisted: '{word}'")
        return FilterResult(passed=True)


class URLPatternFilter(BaseFilter):
    def __init__(self, patterns: list[str]) -> None:
        self._patterns = [p.lower() for p in patterns]

    @property
    def name(self) -> str:
        return "URLPatternFilter"

    def check(self, listing: NormalizedListing) -> FilterResult:
        url = listing.url.lower()
        for p in self._patterns:
            if p in url:
                return FilterResult(passed=False, reason=f"URL contains '{p}'")
        return FilterResult(passed=True)


class FilterPipeline:
    def __init__(self, filters: list[BaseFilter] | None = None) -> None:
        self._filters = filters or []

    def apply(self, listing: NormalizedListing) -> bool:
        for f in self._filters:
            if not f.check(listing).passed:
                return False
        return True

    @classmethod
    def create(
        cls,
        allowed_types: list[str],
        max_price: int,
        min_area: int,
        active_locality_ids: set[str],
        blacklist_words: list[str],
        url_blocked_patterns: list[str] | None = None,
    ) -> "FilterPipeline":
        filters: list[BaseFilter] = [TypeFilter(allowed_types)]
        if url_blocked_patterns:
            filters.append(URLPatternFilter(url_blocked_patterns))
        filters.extend([
            PriceFilter(max_price),
            AreaFilter(min_area),
            LocationFilter(active_locality_ids),
            BlacklistFilter(blacklist_words),
        ])
        return cls(filters)
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_filters.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/filters.py tests/test_filters.py
git commit -m "feat: add filter pipeline (type, price, area, location, blacklist, URL)"
```

---

### Task 5: Cross-portal deduplication

**Files:**
- Create: `src/pipeline/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dedup.py
from src.pipeline.dedup import deduplicate, _normalize_title, _numeric_fingerprint, _price_area_key
from src.models import NormalizedListing


def _make(portal="sreality", portal_id="1", title="Test", price=5000000, area=1000, **kw):
    defaults = dict(
        url="https://example.com", type="pozemek", price_unknown=False,
        area_unknown=False, price_per_m2=5000, location="Baška",
        location_id="baska", coordinates=None,
    )
    defaults.update(kw)
    return NormalizedListing(portal=portal, portal_id=portal_id, title=title,
                             price=price, area_m2=area, **defaults)


def test_normalize_title():
    assert _normalize_title("Prodej rodinného domu 180 m²") == _normalize_title("Prodej rodinneho domu 180 m2")


def test_numeric_fingerprint():
    fp = _numeric_fingerprint("Stavební pozemek 2473 m², cena 7980000")
    assert "2473" in fp
    assert "7980000" in fp


def test_price_area_key():
    assert _price_area_key(7980000, 2473) == "pa_7980000_2473"
    assert _price_area_key(None, 2473) == ""
    assert _price_area_key(50, 2473) == ""  # price too low


def test_dedup_exact_title():
    a = _make(portal="sreality", portal_id="1", title="Stavební pozemek 2473 m²")
    b = _make(portal="bazos", portal_id="2", title="Stavební pozemek 2473 m²")
    result = deduplicate([a, b])
    assert len(result) == 1
    assert result[0].portal == "sreality"  # Higher priority


def test_dedup_price_area_match():
    a = _make(portal="sreality", portal_id="1", title="Nice house", price=7980000, area=2473)
    b = _make(portal="bazos", portal_id="2", title="Different title", price=7980000, area=2473)
    result = deduplicate([a, b])
    assert len(result) == 1
    assert result[0].portal == "sreality"


def test_dedup_no_match():
    a = _make(portal="sreality", portal_id="1", title="House A", price=5000000, area=1000)
    b = _make(portal="bazos", portal_id="2", title="House B", price=3000000, area=500)
    result = deduplicate([a, b])
    assert len(result) == 2


def test_dedup_keeps_higher_priority():
    a = _make(portal="bazos", portal_id="1", title="Same listing")
    b = _make(portal="idnes", portal_id="2", title="Same listing")
    c = _make(portal="sreality", portal_id="3", title="Same listing")
    result = deduplicate([a, b, c])
    assert len(result) == 1
    assert result[0].portal == "sreality"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_dedup.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement dedup**

```python
# src/pipeline/dedup.py
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

    # Build dedup groups: key → list of listings
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
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_dedup.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/dedup.py tests/test_dedup.py
git commit -m "feat: add cross-portal dedup with 5 matching strategies + union-find"
```

---

### Task 6: Data diffing logic

**Files:**
- Create: `src/diff.py`
- Create: `tests/test_diff.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_diff.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement diff logic**

```python
# src/diff.py
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
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2 && python -m pytest tests/test_diff.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/diff.py tests/test_diff.py
git commit -m "feat: add listing diff logic (new, price change, removed detection)"
```

---

## Phase 2: Scrapers

18 portal scrapers. Each follows the same pattern. Can be developed in parallel.

---

### Task 7: Base scraper + HTTP client

**Files:**
- Create: `src/scrapers/__init__.py`
- Create: `src/scrapers/base.py`

- [ ] **Step 1: Implement base scraper**

```python
# src/scrapers/__init__.py
"""Scraper registry."""

from src.scrapers.base import BaseScraper

# Populated as scrapers are added
SCRAPERS: dict[str, type[BaseScraper]] = {}


def register(name: str):
    """Decorator to register a scraper class."""
    def wrapper(cls):
        SCRAPERS[name] = cls
        return cls
    return wrapper
```

```python
# src/scrapers/base.py
"""Base scraper with shared HTTP client and rate limiting."""

import asyncio
import random
from abc import ABC, abstractmethod
from src.models import RawListing

import httpx


class BaseScraper(ABC):
    """Abstract base for all portal scrapers."""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    ]

    def __init__(self, timeout: float = 30.0, delay_range: tuple[float, float] = (1.0, 2.5)):
        self._timeout = timeout
        self._delay_range = delay_range

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": random.choice(self.USER_AGENTS)},
            follow_redirects=True,
        )

    async def _delay(self) -> None:
        await asyncio.sleep(random.uniform(*self._delay_range))

    @abstractmethod
    async def scrape(self, listing_type: str) -> list[RawListing]:
        """Scrape portal for given type. Returns list of raw listings."""
        ...
```

- [ ] **Step 2: Commit**

```bash
git add src/scrapers/
git commit -m "feat: add base scraper with HTTP client and rate limiting"
```

---

### Task 8: Sreality scraper (priority 1, REST API)

**Files:**
- Create: `src/scrapers/sreality.py`

- [ ] **Step 1: Implement Sreality scraper**

Port from v1 `src/scrapers/sreality.py`. Key changes: use `BaseScraper` ABC, return `RawListing`, no SurrealDB.

```python
# src/scrapers/sreality.py
"""Sreality.cz REST API scraper."""

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

SEARCH_CONFIGS = {
    "dum": {
        "category_main_cb": 2,
        "category_type_cb": 1,
        "locality_region_id": 14,  # Moravskoslezsky
    },
    "pozemek": {
        "category_main_cb": 3,
        "category_sub_cb": 19,
        "category_type_cb": 1,
        "locality_region_id": 14,
        "locality_district_id": 8106,  # Frydek-Mistek
    },
    "byt": {
        "category_main_cb": 1,
        "category_type_cb": 1,
        "locality_region_id": 14,
        "locality_district_id": 8119,  # Ostrava-mesto
    },
}

PER_PAGE = 60
MAX_PAGES = 100
API_URL = "https://www.sreality.cz/api/cs/v2/estates"


@register("sreality")
class SrealityScraper(BaseScraper):
    async def scrape(self, listing_type: str) -> list[RawListing]:
        config = SEARCH_CONFIGS.get(listing_type)
        if not config:
            return []

        results = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                params = {**config, "per_page": PER_PAGE, "page": page}
                try:
                    resp = await client.get(API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    break

                estates = data.get("_embedded", {}).get("estates", [])
                if not estates:
                    break

                for estate in estates:
                    hash_id = str(estate.get("hash_id", ""))
                    if not hash_id:
                        continue

                    name = estate.get("name", "")
                    price = estate.get("price", 0)
                    locality = estate.get("locality", "")

                    gps = estate.get("gps", {})
                    coords = None
                    if gps and gps.get("lat") and gps.get("lon"):
                        coords = (gps["lat"], gps["lon"])

                    seo = estate.get("seo", {})
                    detail_url = f"https://www.sreality.cz/detail/{seo.get('category_main_cb', '')}/{seo.get('category_sub_cb', '')}/{seo.get('locality', '')}/{hash_id}"

                    images = []
                    for img in estate.get("_links", {}).get("images", [])[:5]:
                        href = img.get("href", "")
                        if href:
                            images.append(href.replace("{res}", "400x300"))

                    results.append(RawListing(
                        portal="sreality",
                        portal_id=hash_id,
                        title=name,
                        url=detail_url,
                        type_raw=listing_type,
                        price_raw=str(price) if price else None,
                        area_raw=name,  # Area often in title
                        location_raw=locality,
                        coordinates=coords,
                        images=images,
                    ))

                if len(estates) < PER_PAGE:
                    break
                await self._delay()

        return results
```

- [ ] **Step 2: Commit**

```bash
git add src/scrapers/sreality.py
git commit -m "feat: add Sreality REST API scraper"
```

---

### Task 9-24: Remaining 17 scrapers

Each scraper follows the same pattern. Port from v1, adapt to `BaseScraper` + `RawListing`.

**For each portal, create `src/scrapers/{portal}.py`:**

- [ ] **Step 1**: Port scraper from v1 `/Users/davidpleva/Projects/2026/AI-March/reality-fetcher/src/scrapers/{portal}.py`
- [ ] **Step 2**: Adapt to new interfaces: inherit `BaseScraper`, return `list[RawListing]`, use `@register("{portal}")` decorator
- [ ] **Step 3**: Remove any SurrealDB references
- [ ] **Step 4**: Commit

**Portals to implement (in priority order):**

| Task | Portal | File | Parsing |
|------|--------|------|---------|
| 9 | idnes | `src/scrapers/idnes.py` | HTML selectolax |
| 10 | realitymix | `src/scrapers/realitymix.py` | HTML selectolax |
| 11 | bezrealitky | `src/scrapers/bezrealitky.py` | Next.js JSON |
| 12 | bazos | `src/scrapers/bazos.py` | HTML selectolax |
| 13 | realingo | `src/scrapers/realingo.py` | Next.js JSON |
| 14 | eurobydleni | `src/scrapers/eurobydleni.py` | HTML selectolax |
| 15 | sousede | `src/scrapers/sousede.py` | HTML selectolax |
| 16 | remaxcz | `src/scrapers/remaxcz.py` | HTML + DMS GPS |
| 17 | realitycz | `src/scrapers/realitycz.py` | HTML + CSS GPS |
| 18 | realcity | `src/scrapers/realcity.py` | HTML selectolax |
| 19 | realhit | `src/scrapers/realhit.py` | JSON-LD |
| 20 | century21 | `src/scrapers/century21.py` | HTML selectolax |
| 21 | moravskereality | `src/scrapers/moravskereality.py` | HTML selectolax |
| 22 | rksting | `src/scrapers/rksting.py` | HTML selectolax |
| 23 | boreality | `src/scrapers/boreality.py` | HTML selectolax |
| 24 | realityregio | `src/scrapers/realityregio.py` | HTML selectolax |
| 25 | mmreality | `src/scrapers/mmreality.py` | HTML selectolax |

**Key reference**: v1 source at `/Users/davidpleva/Projects/2026/AI-March/reality-fetcher/src/scrapers/`. See specs.md Section 6.2 for exact URLs, selectors, pagination, and search params per portal.

**Commit after each scraper** with message: `feat: add {portal} scraper`

---

## Phase 3: Email Notifications

---

### Task 26: Gmail SMTP email sender

**Files:**
- Create: `src/notifications/__init__.py`
- Create: `src/notifications/email_sender.py`

- [ ] **Step 1: Implement email sender**

```python
# src/notifications/__init__.py
# empty

# src/notifications/email_sender.py
"""Send email notifications via Gmail SMTP."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_report_email(
    area_name: str,
    recipients: list[str],
    new: list[dict],
    changed: list[dict],
    removed: list[dict],
    dashboard_url: str,
) -> None:
    """Send email notification for listing changes."""
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_pass:
        print("GMAIL_USER or GMAIL_APP_PASSWORD not set, skipping email")
        return

    subject = f"[Reality Monitor] {area_name}: "
    parts = []
    if new:
        parts.append(f"{len(new)} nové")
    if changed:
        parts.append(f"{len(changed)} změna ceny")
    if removed:
        parts.append(f"{len(removed)} smazané")
    subject += ", ".join(parts)

    html = _build_html(area_name, new, changed, removed, dashboard_url)
    plain = _build_plain(area_name, new, changed, removed, dashboard_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, recipients, msg.as_string())
    print(f"Email sent to {recipients}")


def _format_price(price: int | None) -> str:
    if price is None:
        return "Cena na vyžádání"
    return f"{price:,} Kč".replace(",", " ")


def _build_html(area: str, new: list, changed: list, removed: list, url: str) -> str:
    sections = [f"<h2>Reality Monitor — {area}</h2>"]
    sections.append(f'<p><a href="{url}">Otevřít dashboard</a></p>')

    if new:
        sections.append("<h3>Nové inzeráty</h3><ul>")
        for l in new:
            price = _format_price(l.get("price"))
            area_m2 = f'{l.get("area_m2", "?")} m²'
            sections.append(
                f'<li><a href="{l["url"]}">{l["title"]}</a> — {l.get("location", "")} — '
                f'{price} — {area_m2}</li>'
            )
        sections.append("</ul>")

    if changed:
        sections.append("<h3>Změny cen</h3><ul>")
        for l in changed:
            history = l.get("price_history", [])
            if len(history) >= 2:
                old_p = history[-2]["price"]
                new_p = history[-1]["price"]
                if old_p and new_p and old_p != 0:
                    pct = ((new_p - old_p) / old_p) * 100
                    arrow = "↓" if pct < 0 else "↑"
                    color = "green" if pct < 0 else "red"
                    sections.append(
                        f'<li><a href="{l["url"]}">{l["title"]}</a> — '
                        f'{_format_price(old_p)} → {_format_price(new_p)} '
                        f'<span style="color:{color}">{arrow} {pct:+.1f}%</span></li>'
                    )
        sections.append("</ul>")

    if removed:
        sections.append("<h3>Smazané</h3><ul>")
        for l in removed:
            sections.append(f'<li>{l["title"]} — {l.get("location", "")} — byl {_format_price(l.get("price"))}</li>')
        sections.append("</ul>")

    return "\n".join(sections)


def _build_plain(area: str, new: list, changed: list, removed: list, url: str) -> str:
    lines = [f"Reality Monitor — {area}", f"Dashboard: {url}", ""]
    if new:
        lines.append(f"Nové ({len(new)}):")
        for l in new:
            lines.append(f"  • {l['title']} — {_format_price(l.get('price'))} — {l['url']}")
        lines.append("")
    if changed:
        lines.append(f"Změny cen ({len(changed)}):")
        for l in changed:
            lines.append(f"  • {l['title']} — {l['url']}")
        lines.append("")
    if removed:
        lines.append(f"Smazané ({len(removed)}):")
        for l in removed:
            lines.append(f"  • {l['title']}")
    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add src/notifications/
git commit -m "feat: add Gmail SMTP email sender with HTML notifications"
```

---

## Phase 4: HTML Dashboard

---

### Task 27: Static site generator

**Files:**
- Create: `src/site_generator.py`
- Create: `site/index.html`

- [ ] **Step 1: Implement site generator**

Create `src/site_generator.py` that generates self-contained HTML files with:
- Inline CSS (responsive, clean design)
- Inline JS (filtering, sorting, localStorage state persistence)
- JSON data embedded in `<script>` tag
- Filter bar: status, type, location dropdown, price range, area range, sort
- Listing table with: type badge, location (Maps link), area, price, price/m², price change (yellow + arrow + %), date, portal link
- NEW badge for latest additions
- Removed section collapsed at bottom
- No external dependencies

The file will be ~400 lines. Key template sections:

**CSS**: Sticky filter bar, yellow `.price-changed` class, green `.new-badge`, strikethrough `.removed`, responsive table
**JS**: `filterAndSort()` reads filter state → filters `DATA.listings` → renders rows → saves to localStorage. `loadFilters()` restores from localStorage on page load.
**Data**: `const DATA = ${json.dumps(area_data)};` embedded in script tag.

- [ ] **Step 2: Create site/index.html landing page**

```html
<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reality Monitor</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
    a { display: block; padding: 20px; margin: 10px 0; background: #f0f0f0; border-radius: 8px;
        text-decoration: none; color: #333; font-size: 1.2em; }
    a:hover { background: #e0e0e0; }
  </style>
</head>
<body>
  <h1>Reality Monitor</h1>
  <a href="fm.html">Frýdek-Místek — domy a pozemky</a>
  <a href="poruba.html">Ostrava-Poruba — byty</a>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add src/site_generator.py site/index.html
git commit -m "feat: add static HTML dashboard generator with filters and price change display"
```

---

## Phase 5: Orchestrator + GitHub Actions

---

### Task 28: Main orchestrator

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Implement main orchestrator**

Wire together: config loading → scraping all portals → per-area normalization + filtering + dedup → diffing → save data → generate HTML → send email.

Follow the pseudocode from specs.md Section 11.9. Key flow:

```python
# src/main.py
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
from src.scrapers import SCRAPERS

# Import all scrapers to trigger registration
import src.scrapers.sreality  # noqa
# ... all 18 imports

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
        for portal_name, raw_listings in all_raw.items():
            for raw in raw_listings:
                normalized = normalize_listing(raw, aliases, localities)
                if normalized is None:
                    continue
                if not pipeline.apply(normalized):
                    continue
                candidates.append(normalized)

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
```

- [ ] **Step 2: Commit**

```bash
git add src/main.py
git commit -m "feat: add main orchestrator (scrape → filter → dedup → diff → email → generate)"
```

---

### Task 29: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/scrape.yml`

- [ ] **Step 1: Create workflow**

```yaml
# .github/workflows/scrape.yml
name: Scrape Reality Portals

on:
  schedule:
    - cron: '0 5 * * *'   # 07:00 CET
    - cron: '0 16 * * *'  # 18:00 CET
  workflow_dispatch:

permissions:
  contents: write

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scraper
        run: python -m src.main
        env:
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}

      - name: Commit and push changes
        run: |
          git config user.name "Reality Bot"
          git config user.email "bot@reality-fetcher"
          git add data/ site/
          git diff --cached --quiet || git commit -m "Update $(date -u +%Y-%m-%d_%H:%M)"
          git push
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scrape.yml
git commit -m "feat: add GitHub Actions workflow (2x daily cron + manual trigger)"
```

---

### Task 30: Final integration test + README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Run full pipeline locally**

```bash
cd /Users/davidpleva/Projects/2026/AI-March/reality-fetcher-v2
pip install -r requirements.txt
python -m src.main
```

Verify: `data/fm.json` and `data/poruba.json` are populated, `site/fm.html` and `site/poruba.html` are generated.

- [ ] **Step 2: Open dashboard in browser and verify**

```bash
open site/fm.html
```

Check: filters work, price changes show yellow, Maps links work, NEW badges appear, removed section is collapsed.

- [ ] **Step 3: Create README**

Brief README with: what it does, how to set up Gmail App Password, how to deploy (push to GitHub, enable Pages, add secrets), manual trigger command.

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions"
```

---

## Execution Notes

- **Tasks 1-6** (Phase 1) are sequential — each builds on the previous
- **Tasks 8-25** (Phase 2, scrapers) can run in parallel — each scraper is independent
- **Tasks 26-29** (Phases 3-5) depend on Phase 1 being complete
- **Task 30** requires everything to be done

Total: ~30 tasks. Phase 1 is the critical path. Scrapers are the bulk of the work but are mechanical ports from v1.
