"""Bazos.cz scraper using HTML parsing."""

from __future__ import annotations

import re
from urllib.parse import urlencode

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://reality.bazos.cz"

SEARCH_CONFIGS = {
    "dum": {
        "path": "/prodam/dum/",
        "params": {"hlokalita": "73801", "humkreis": "25", "cenado": "10000000"},
    },
    "pozemek": {
        "path": "/prodam/pozemek/",
        "params": {"hlokalita": "73801", "humkreis": "25", "cenado": "10000000"},
    },
    "byt": {
        "path": "/prodam/byt/",
        "params": {"hlokalita": "73801", "humkreis": "25", "cenado": "10000000"},
    },
}

PER_PAGE = 20
MAX_PAGES = 50

_ID_RE = re.compile(r"/inzerat/(\d+)/")
_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")


@register("bazos")
class BazosScraper(BaseScraper):
    """Bazos.cz scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        config = SEARCH_CONFIGS.get(listing_type)
        if not config:
            return []

        base_path = config["path"]
        query_string = urlencode(config["params"])

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(MAX_PAGES):
                offset = page * PER_PAGE
                if offset == 0:
                    url = f"{BASE_URL}{base_path}?{query_string}"
                else:
                    url = f"{BASE_URL}{base_path}{offset}/?{query_string}"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                listings = tree.css("div.inzeraty.inzeratyflex")
                if not listings:
                    break

                for node in listings:
                    raw = _parse_listing(node, listing_type)
                    if raw is not None:
                        results.append(raw)

                if len(listings) < PER_PAGE:
                    break
                await self._delay()

        return results


def _parse_listing(node, listing_type: str) -> RawListing | None:
    """Parse a single Bazos listing div."""
    title_link = node.css_first("h2.nadpis a") or node.css_first("h2 a")
    if title_link is None:
        return None

    title = title_link.text(strip=True)
    href = title_link.attributes.get("href", "")
    if href.startswith("/"):
        url = BASE_URL + href
    elif href.startswith("http"):
        url = href
    else:
        return None

    id_match = _ID_RE.search(href)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    # Description
    desc_node = node.css_first("div.popis")
    description = desc_node.text(strip=True) if desc_node else ""

    # Price
    price_raw = None
    price_node = node.css_first("div.inzeratycena b span")
    if price_node:
        price_raw = price_node.text(strip=True)

    # Location
    location_raw = ""
    loc_node = node.css_first("div.inzeratylok")
    if loc_node:
        location_raw = loc_node.text(strip=True)

    # Image
    images = []
    img_node = node.css_first("div.inzeratynadpis img") or node.css_first("img.obrazek")
    if img_node:
        src = img_node.attributes.get("src", "")
        if src:
            if src.startswith("/"):
                src = BASE_URL + src
            images.append(src)

    # Area from title or description
    area_raw = None
    combined = f"{title} {description}"
    area_matches = _AREA_RE.findall(combined)
    if area_matches:
        area_raw = area_matches[-1].strip() + " m2"

    return RawListing(
        portal="bazos",
        portal_id=portal_id,
        title=title,
        url=url,
        type_raw=listing_type,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        description=description,
        images=images,
    )
