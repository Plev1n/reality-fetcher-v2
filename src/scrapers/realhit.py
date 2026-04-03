"""RealHit.cz scraper using JSON-LD extraction."""

from __future__ import annotations

import json
import re

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://realhit.cz"

SEARCH_CONFIGS = {
    "dum": "/prodej/domy/frydek-mistek/",
    "pozemek": "/prodej/pozemky/frydek-mistek/",
    "byt": "/prodej/byty/frydek-mistek/",
}

PER_PAGE = 20
MAX_PAGES = 30

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")
_JSONLD_RE = re.compile(r'<script\s+type="application/ld\+json">(.*?)</script>', re.DOTALL)


@register("realhit")
class RealhitScraper(BaseScraper):
    """realhit.cz scraper via JSON-LD extraction."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + path
                if page > 1:
                    url += f"strana/{page}/"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception:
                    break

                # Find JSON-LD ItemList
                items = []
                for match in _JSONLD_RE.finditer(resp.text):
                    try:
                        data = json.loads(match.group(1))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and data.get("@type") == "ItemList":
                        items = data.get("itemListElement", [])
                        break
                    elif isinstance(data, list):
                        for entry in data:
                            if isinstance(entry, dict) and entry.get("@type") == "ItemList":
                                items = entry.get("itemListElement", [])
                                break
                        if items:
                            break

                if not items:
                    break

                for item_wrapper in items:
                    item = item_wrapper.get("item", item_wrapper)
                    raw = _parse_jsonld_item(item, listing_type)
                    if raw is not None:
                        results.append(raw)

                if len(items) < PER_PAGE:
                    break
                await self._delay()

        return results


def _parse_jsonld_item(item: dict, listing_type: str) -> RawListing | None:
    """Parse a JSON-LD Product item."""
    url = item.get("url", "")
    title = item.get("name", "")
    if not url or not title:
        return None

    # Portal ID from URL slug
    portal_id = url.rstrip("/").split("/")[-1] if url else ""
    if not portal_id:
        return None

    # Price
    price_raw = None
    offers = item.get("offers", {})
    if isinstance(offers, dict):
        price = offers.get("price")
        if price is not None:
            try:
                price_int = int(float(str(price)))
                if price_int > 0:
                    price_raw = str(price_int)
            except (ValueError, TypeError):
                pass

    # Area
    area_raw = None
    area_match = _AREA_RE.search(title)
    if area_match:
        area_raw = area_match.group(1).replace("\xa0", " ").strip() + " m2"

    # Location
    location_raw = ""
    address = item.get("address", {})
    if isinstance(address, dict):
        locality = address.get("addressLocality", "")
        street = address.get("streetAddress", "")
        if street and locality:
            location_raw = f"{street}, {locality}"
        elif locality:
            location_raw = locality

    # GPS
    coords = None
    geo = item.get("geo", {})
    if isinstance(geo, dict):
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is not None and lon is not None:
            try:
                coords = (float(lat), float(lon))
            except (ValueError, TypeError):
                pass

    # Image
    images = []
    image = item.get("image", "")
    if isinstance(image, str) and image:
        images.append(image)
    elif isinstance(image, list) and image:
        images.append(image[0])

    description = item.get("description", "")

    return RawListing(
        portal="realhit",
        portal_id=portal_id,
        title=title,
        url=url,
        type_raw=title,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        description=description,
        coordinates=coords,
        images=images,
    )
