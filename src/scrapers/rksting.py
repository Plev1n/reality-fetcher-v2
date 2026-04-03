"""RK Sting scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.rksting.cz"

SEARCH_CONFIGS = {
    "dum": "/rodinne-domy-moravskoslezsky-kraj/",
    "pozemek": "/pozemky-moravskoslezsky-kraj/",
    "byt": "/byty-moravskoslezsky-kraj/",
}

PER_PAGE = 8
MAX_PAGES = 50

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")
_ID_RE = re.compile(r"-(\d+)/$")


@register("rksting")
class RkstingScraper(BaseScraper):
    """rksting.cz scraper via HTML parsing."""

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
                    params["p"] = str(page)

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("div.result-row")
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
    """Parse a div.result-row card."""
    title_el = card.css_first("h2.heading")
    if title_el is None:
        return None
    title = title_el.text(strip=True)

    btn_link = card.css_first("div.button a")
    if btn_link is None:
        return None
    href = btn_link.attributes.get("href", "")
    if not href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    id_match = _ID_RE.search(href)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    # Price
    price_raw = None
    price_el = card.css_first("div.price-col")
    if price_el:
        price_raw = price_el.text(strip=True)

    # Location
    location_raw = ""
    loc_el = card.css_first("div.loc-col")
    if loc_el:
        location_raw = loc_el.text(strip=True)

    # Area from size-col
    area_raw = None
    size_el = card.css_first("div.size-col")
    if size_el:
        size_text = size_el.text(strip=True)
        area_matches = _AREA_RE.findall(size_text)
        if area_matches:
            area_raw = area_matches[-1].strip() + " m2"
    if not area_raw:
        area_matches = _AREA_RE.findall(title)
        if area_matches:
            area_raw = area_matches[-1].strip() + " m2"

    # Image
    images = []
    img = card.css_first("img.rt-prop-image")
    if img:
        src = img.attributes.get("src", "")
        if src:
            if src.startswith("/"):
                src = BASE_URL + src
            images.append(src)

    return RawListing(
        portal="rksting",
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
