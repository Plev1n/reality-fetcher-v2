"""Reality Sousede (reality.sousede.cz) scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://reality.sousede.cz"

SEARCH_CONFIGS = {
    "dum": "/prodej/rodinne-domy/moravskoslezsky-kraj/frydek-mistek/",
    "pozemek": "/prodej/pozemky/moravskoslezsky-kraj/frydek-mistek/",
    "byt": "/prodej/byty/moravskoslezsky-kraj/frydek-mistek/",
}

PER_PAGE = 20
MAX_PAGES = 30

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")
_ID_RE = re.compile(r"-(\d+)\.html$")


@register("sousede")
class SousedeScraper(BaseScraper):
    """reality.sousede.cz scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + path
                params = {}
                if page > 1:
                    params["strana"] = str(page)

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("div.i-estate")
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
    """Parse a div.i-estate card."""
    title_el = card.css_first("div.title h3 a")
    if title_el is None:
        return None
    title = title_el.text(strip=True)
    href = title_el.attributes.get("href", "")
    if not href:
        return None
    url = href if href.startswith("http") else BASE_URL + href

    id_match = _ID_RE.search(href)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    # Price
    price_raw = None
    price_el = card.css_first("div.price div.value")
    if price_el:
        price_raw = price_el.text(strip=True)

    # Location
    location_raw = ""
    loc_el = card.css_first("div.location")
    if loc_el:
        location_raw = loc_el.text(strip=True)
    if not location_raw:
        parts = re.split(r"m[²2]\s*", title)
        if len(parts) > 1 and parts[-1].strip():
            location_raw = parts[-1].strip()

    # Area
    area_raw = None
    area_match = _AREA_RE.search(title)
    if area_match:
        area_raw = area_match.group(1).replace("\xa0", " ").strip() + " m2"

    # Description
    description = ""
    desc_el = card.css_first("div.desc p")
    if desc_el:
        description = desc_el.text(strip=True)

    # Image
    images = []
    img = card.css_first("div.estate-image picture img")
    if img:
        src = img.attributes.get("src", "")
        if src:
            images.append(src)

    return RawListing(
        portal="sousede",
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
