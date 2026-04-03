"""Century 21 Czech (century21.cz) scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.century21.cz"

SEARCH_CONFIGS = {
    "dum": "/nemovitosti?typ=prodej&druh=domy&region=moravskoslezsky-kraj",
    "pozemek": "/nemovitosti?typ=prodej&druh=pozemky&region=moravskoslezsky-kraj",
    "byt": "/nemovitosti?typ=prodej&druh=byty&region=moravskoslezsky-kraj",
}

PER_PAGE = 20
MAX_PAGES = 20

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")
_UUID_RE = re.compile(r"id=([a-f0-9-]{36})")


@register("century21")
class Century21Scraper(BaseScraper):
    """century21.cz scraper via server-rendered HTML."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        base_path = SEARCH_CONFIGS.get(listing_type)
        if not base_path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + base_path
                if page > 1:
                    url += f"&page={page}"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("article")
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
    """Parse an <article> card."""
    link_el = card.css_first("a[href*='/nemovitosti/']")
    if link_el is None:
        return None
    href = link_el.attributes.get("href", "")
    if not href or "/nemovitosti/" not in href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    # Portal ID (UUID)
    id_match = _UUID_RE.search(href)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    # Title
    title_el = card.css_first("h3")
    title = title_el.text(strip=True) if title_el else ""
    if not title:
        return None

    # Price
    price_raw = None
    for el in card.css("div"):
        text = el.text(strip=True)
        if "Kč" in text and len(text) < 30:
            price_raw = text
            break

    # Location
    location_raw = ""
    loc_el = card.css_first("p[translate='no']")
    if loc_el:
        location_raw = loc_el.text(strip=True)

    # Area
    area_raw = None
    area_match = _AREA_RE.search(title)
    if area_match:
        area_raw = area_match.group(1).replace("\xa0", " ").strip() + " m2"

    # Image
    images = []
    img = card.css_first("img[src*='igluu.cz'], img[src*='file']")
    if img:
        src = img.attributes.get("src", "")
        if src:
            images.append(src)

    return RawListing(
        portal="century21",
        portal_id=portal_id,
        title=title,
        url=url,
        type_raw=title,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        images=images,
    )
