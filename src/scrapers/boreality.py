"""Boreality.cz scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.boreality.cz"

SEARCH_CONFIGS = {
    "dum": "/prodej/rodinne-domy/moravskoslezsky/",
    "pozemek": "/prodej/pozemky/moravskoslezsky/",
    "byt": "/prodej/byty/moravskoslezsky/",
}

PER_PAGE = 20
MAX_PAGES = 50

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")
_ID_RE = re.compile(r"-(\d+)/$")


@register("boreality")
class BorealityScraper(BaseScraper):
    """boreality.cz scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                if page == 1:
                    url = BASE_URL + path
                else:
                    url = BASE_URL + path + f"{page}/"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("article.estateListItem")
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
    """Parse an article.estateListItem card."""
    title_el = card.css_first("h2")
    if title_el is None:
        return None
    title = title_el.text(strip=True)

    link = card.css_first("a[href*='/reality/']")
    if link is None:
        return None
    href = link.attributes.get("href", "")
    if not href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    id_match = _ID_RE.search(href)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    # Price
    price_raw = None
    for node in card.css("*"):
        text = node.text(strip=True)
        if "Kč" in text and len(text) < 100:
            price_raw = text
            break

    # Location from title (after last comma)
    location_raw = ""
    if "," in title:
        location_raw = title.rsplit(",", 1)[-1].strip().rstrip(".")

    # Area
    area_raw = None
    area_matches = _AREA_RE.findall(title)
    if area_matches:
        area_raw = area_matches[-1].strip() + " m2"

    # Image
    images = []
    img = card.css_first("img")
    if img:
        src = img.attributes.get("data-src", "") or img.attributes.get("src", "")
        if src:
            if src.startswith("/"):
                src = BASE_URL + src
            images.append(src)

    return RawListing(
        portal="boreality",
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
