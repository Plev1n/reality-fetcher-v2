"""RealCity.cz scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.realcity.cz"

SEARCH_CONFIGS = {
    "dum": "/prodej-domu/frydek-mistek-82",
    "pozemek": "/prodej-pozemku/frydek-mistek-82",
    "byt": "/prodej-bytu/frydek-mistek-82",
}

PER_PAGE = 20
MAX_PAGES = 20

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")


@register("realcity")
class RealcityScraper(BaseScraper):
    """realcity.cz scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + path
                params = {"list-perPage": "20"}
                if page > 1:
                    params["list-page"] = str(page)

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("div.media.advertise.item")
                if not cards:
                    break

                for card in cards:
                    raw = _parse_card(card, listing_type)
                    if raw is not None:
                        results.append(raw)

                if len(cards) < PER_PAGE:
                    break
                await self._delay()

        return results


def _parse_card(card, listing_type: str) -> RawListing | None:
    """Parse a div.media.advertise.item card."""
    portal_id = card.attributes.get("data-advertise", "")
    if not portal_id:
        return None

    title_el = card.css_first("div.title a")
    if title_el is None:
        return None
    title = title_el.text(strip=True)
    href = title_el.attributes.get("href", "")
    if not href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    # Price
    price_raw = None
    price_el = card.css_first("div.price span.highlight")
    if price_el:
        price_raw = price_el.text(strip=True)

    # Location
    location_raw = ""
    addr_el = card.css_first("div.address")
    if addr_el:
        location_raw = addr_el.text(strip=True)

    # Area
    area_raw = None
    area_match = _AREA_RE.search(title)
    if area_match:
        area_raw = area_match.group(1).replace("\xa0", " ").strip() + " m2"

    # Description
    description = ""
    desc_el = card.css_first("div.description")
    if desc_el:
        description = desc_el.text(strip=True)

    # Image
    images = []
    img = card.css_first("img.media-object")
    if img:
        src = img.attributes.get("src", "")
        if src:
            images.append(src)

    return RawListing(
        portal="realcity",
        portal_id=portal_id,
        title=title,
        url=url,
        type_raw=title,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        description=description,
        images=images,
    )
