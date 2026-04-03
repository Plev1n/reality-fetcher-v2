"""Sreality.cz REST API scraper."""

from __future__ import annotations

import re

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

API_URL = "https://www.sreality.cz/api/cs/v2/estates"

SEARCH_CONFIGS = {
    "dum": {
        "category_main_cb": 2,
        "category_type_cb": 1,
        "locality_region_id": 14,  # Moravskoslezsky
    },
    "pozemek": {
        "category_main_cb": 3,
        "category_sub_cb": 19,  # stavebni parcely
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

# URL slug mappings
_MAIN_SLUG = {1: "byt", 2: "dum", 3: "pozemek", 4: "komercni", 5: "ostatni"}
_TYPE_SLUG = {1: "prodej", 2: "pronajem", 3: "drazba", 4: "podil"}
_SUB_SLUG = {
    33: "rodinny", 37: "vila", 39: "chalupa", 43: "na-klic",
    44: "zemedelska-usedlost", 46: "pamatka-jine",
    2: "1-kk", 3: "1-1", 4: "2-kk", 5: "2-1", 6: "3-kk", 7: "3-1",
    8: "4-kk", 9: "4-1", 10: "5-kk", 11: "5-1", 12: "6-a-vice", 47: "atypicky",
    19: "bydleni", 22: "komercni", 21: "pole", 20: "lesy", 18: "zahrada", 23: "ostatni",
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
                    raw = _parse_estate(estate, listing_type)
                    if raw is not None:
                        results.append(raw)

                if len(estates) < PER_PAGE:
                    break
                await self._delay()

        return results


def _parse_estate(estate: dict, listing_type: str) -> RawListing | None:
    """Parse a single estate from the Sreality API response."""
    hash_id = estate.get("hash_id")
    if not hash_id:
        return None

    name = estate.get("name", "")
    locality = estate.get("locality", "")

    # Price
    price = estate.get("price")
    if isinstance(price, (int, float)) and price > 0:
        price_raw = f"{int(price)} Kc"
    else:
        price_raw = None

    # GPS
    coords = None
    gps = estate.get("gps")
    if isinstance(gps, dict):
        lat, lon = gps.get("lat"), gps.get("lon")
        if lat is not None and lon is not None:
            coords = (float(lat), float(lon))

    # Build URL from SEO block
    seo = estate.get("seo", {})
    locality_seo = seo.get("locality", "")
    main_id = seo.get("category_main_cb")
    type_id = seo.get("category_type_cb")
    sub_id = seo.get("category_sub_cb")

    main_slug = main_id if isinstance(main_id, str) else _MAIN_SLUG.get(main_id, "")
    type_slug = type_id if isinstance(type_id, str) else _TYPE_SLUG.get(type_id, "prodej")
    sub_slug = sub_id if isinstance(sub_id, str) else _SUB_SLUG.get(sub_id, "")

    if locality_seo and main_slug:
        url = f"https://www.sreality.cz/detail/{type_slug}/{main_slug}/{sub_slug}/{locality_seo}/{hash_id}"
    else:
        url = f"https://www.sreality.cz/detail/prodej/{hash_id}"

    # Images
    images = []
    for img in estate.get("_links", {}).get("images", [])[:5]:
        href = img.get("href", "")
        if href:
            images.append(href.replace("{res}", "400x300"))

    # Area from name
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
        location_raw=locality,
        address_raw=locality,
        coordinates=coords,
        images=images,
    )
