"""Realingo.cz scraper using __NEXT_DATA__ JSON extraction."""

from __future__ import annotations

import json
import re

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.realingo.cz"

SEARCH_CONFIGS = {
    "dum": "/prodej_domy/Okres_Fr%C3%BDdek-M%C3%ADstek/",
    "pozemek": "/prodej_pozemky/Okres_Fr%C3%BDdek-M%C3%ADstek/",
    "byt": "/prodej_byty/Okres_Fr%C3%BDdek-M%C3%ADstek/",
}

PER_PAGE = 40
MAX_PAGES = 20

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

_CATEGORY_LABELS = {
    "HOUSE_FAMILY": "Rodinny dum",
    "HOUSE_VILLA": "Vila",
    "HOUSE_COTTAGE": "Chalupa",
    "HOUSE_FARM": "Zemedelska usedlost",
    "HOUSE_OTHER": "Dum",
    "LAND_RESIDENTIAL": "Stavebni pozemek",
    "LAND_COMMERCIAL": "Komercni pozemek",
    "LAND_HOUSING": "Stavebni pozemek",
    "LAND_OTHER": "Pozemek",
    "FLAT_1KK": "Byt 1+kk", "FLAT_1_1": "Byt 1+1",
    "FLAT_2KK": "Byt 2+kk", "FLAT_2_1": "Byt 2+1",
    "FLAT_3KK": "Byt 3+kk", "FLAT_3_1": "Byt 3+1",
    "FLAT_4KK": "Byt 4+kk", "FLAT_4_1": "Byt 4+1",
    "FLAT_OTHER": "Byt",
}


@register("realingo")
class RealingoScraper(BaseScraper):
    """realingo.cz scraper via __NEXT_DATA__ JSON."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + path
                if page > 1:
                    url += f"{page}_strana/"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception:
                    break

                match = _NEXT_DATA_RE.search(resp.text)
                if not match:
                    break

                try:
                    next_data = json.loads(match.group(1))
                    store = next_data["props"]["pageProps"]["store"]
                    offer_list = store["offer"]["list"]
                    items = offer_list.get("data", [])
                    total = offer_list.get("total", 0)
                except (json.JSONDecodeError, KeyError, TypeError):
                    break

                if not items:
                    break

                for item in items:
                    raw = _parse_item(item, listing_type)
                    if raw is not None:
                        results.append(raw)

                if page * PER_PAGE >= total:
                    break
                await self._delay()

        return results


def _parse_item(item: dict, listing_type: str) -> RawListing | None:
    """Parse a listing object from __NEXT_DATA__."""
    portal_id = str(item.get("id", ""))
    if not portal_id:
        return None

    item_url = item.get("url", "")
    full_url = BASE_URL + item_url if item_url else ""
    if not full_url:
        return None

    category = item.get("category", "")
    label = _CATEGORY_LABELS.get(category, category)
    location = item.get("location", {})
    address = location.get("address", "")
    title = f"{label}, {address}" if address else label

    # Price
    price_data = item.get("price", {})
    price_raw = None
    price_total = price_data.get("total")
    if price_total is not None:
        price_raw = str(price_total)

    # Area
    area_data = item.get("area", {})
    plot_area = area_data.get("plot")
    main_area = area_data.get("main")
    area_raw = None
    if plot_area:
        area_raw = f"{plot_area} m2"
    elif main_area:
        area_raw = f"{main_area} m2"

    # Image
    images = []
    photos = item.get("photos", {})
    main_photo = photos.get("main")
    if main_photo:
        images.append(f"{BASE_URL}/static/images/{main_photo}.jpg")

    # GPS
    coords = None
    lat = location.get("latitude")
    lon = location.get("longitude")
    if lat is not None and lon is not None:
        coords = (lat, lon)

    return RawListing(
        portal="realingo",
        portal_id=portal_id,
        title=title,
        url=full_url,
        type_raw=category,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=address,
        address_raw=address or None,
        coordinates=coords,
        images=images,
    )
