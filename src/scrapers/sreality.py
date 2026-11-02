"""Sreality.cz REST API scraper (api/v1/estates/search, since 2026-10)."""

from __future__ import annotations

import re

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

API_URL = "https://www.sreality.cz/api/v1/estates/search"

# District/region IDs changed with the v1 API (FM was 8106, now 61).
SEARCH_CONFIGS = {
    "dum": {
        "category_main_cb": 2,
        "category_type_cb": 1,
        "locality_district_id": 61,  # Frydek-Mistek
    },
    "pozemek": {
        "category_main_cb": 3,
        "category_sub_cb": 19,  # bydleni (stavebni parcely)
        "category_type_cb": 1,
        "locality_district_id": 61,
    },
    "byt": {
        "category_main_cb": 1,
        "category_type_cb": 1,
        "locality_district_id": 65,  # Ostrava-mesto
    },
}

PER_PAGE = 60
MAX_PAGES = 50

_MAIN_SLUG = {1: "byt", 2: "dum", 3: "pozemek", 4: "komercni", 5: "ostatni"}
_TYPE_SLUG = {1: "prodej", 2: "pronajem", 3: "drazba", 4: "podil"}
_SUB_SLUG = {
    33: "chata", 35: "pamatka-jine", 37: "rodinny", 39: "vila", 40: "na-klic",
    43: "chalupa", 44: "zemedelska-usedlost", 54: "vicegeneracni-dum",
    19: "bydleni", 18: "komercni", 20: "pole", 21: "lesy", 23: "zahrada",
}

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")


@register("sreality")
class SrealityScraper(BaseScraper):
    """Sreality.cz scraper via public REST API."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        config = SEARCH_CONFIGS.get(listing_type)
        if not config:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(MAX_PAGES):
                params = {**config, "limit": PER_PAGE, "offset": page * PER_PAGE}
                try:
                    resp = await client.get(API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    break

                estates = data.get("results") or []
                for estate in estates:
                    raw = parse_estate(estate, listing_type)
                    if raw is not None:
                        results.append(raw)

                total = (data.get("pagination") or {}).get("total")
                if len(estates) < PER_PAGE or (total is not None and (page + 1) * PER_PAGE >= total):
                    break
                await self._delay()

        return results


def _val(x) -> int | None:
    if isinstance(x, dict):
        return x.get("value")
    return x if isinstance(x, int) else None


def parse_estate(estate: dict, listing_type: str) -> RawListing | None:
    """Parse one estate from the v1 search response."""
    hash_id = estate.get("hash_id")
    if not hash_id:
        return None

    name = estate.get("advert_name") or estate.get("name") or ""
    loc = estate.get("locality") or {}
    city = loc.get("city") or ""
    citypart = loc.get("citypart") or ""
    location = f"{city} - {citypart}" if citypart and citypart != city else city

    price = estate.get("price_czk") or estate.get("price")
    price_raw = f"{int(price)} Kc" if isinstance(price, (int, float)) and price > 1 else None

    coords = None
    lat, lon = loc.get("gps_lat"), loc.get("gps_lon")
    if lat is not None and lon is not None:
        coords = (float(lat), float(lon))

    main_slug = _MAIN_SLUG.get(_val(estate.get("category_main_cb")), "dum")
    type_slug = _TYPE_SLUG.get(_val(estate.get("category_type_cb")), "prodej")
    sub_slug = _SUB_SLUG.get(_val(estate.get("category_sub_cb")), "x")
    city_seo = loc.get("city_seo_name") or "x"
    url = f"https://www.sreality.cz/detail/{type_slug}/{main_slug}/{sub_slug}/{city_seo}/{hash_id}"

    images = []
    for src in (estate.get("advert_images") or [])[:5]:
        if isinstance(src, str) and src:
            images.append("https:" + src if src.startswith("//") else src)

    area_raw = None
    area_matches = _AREA_RE.findall(name)
    if area_matches:
        area_raw = area_matches[-1].strip() + " m2"

    return RawListing(
        portal="sreality",
        portal_id=str(hash_id),
        title=name,
        url=url,
        type_raw=listing_type,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location,
        address_raw=location,
        coordinates=coords,
        images=images,
    )
