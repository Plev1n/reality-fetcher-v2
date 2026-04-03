"""Reality Regio scraper using HTML parsing.

NOTE: This portal mixes prodej and pronajem listings.
Only listings with type "prodej" are yielded.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.realityregio.cz"

SEARCH_CONFIGS = {
    "dum": "/reality/moravskoslezsky/",
    "pozemek": "/pozemky/moravskoslezsky/",
    "byt": "/byty/moravskoslezsky/",
}

PER_PAGE = 20
MAX_PAGES = 50

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")
_ID_RE = re.compile(r"-(\d+)/?$")


@register("realityregio")
class RealityregioScraper(BaseScraper):
    """realityregio.cz scraper via HTML parsing."""

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
                    url = BASE_URL + path + f"page-{page}/"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("article.list-items__item__in")
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
    """Parse an article.list-items__item__in card.

    Filters out non-prodej listings (pronajem etc.).
    """
    # Check listing type
    type_el = card.css_first("strong.list-items__item__type")
    if type_el:
        if type_el.text(strip=True).lower() != "prodej":
            return None

    title_link = card.css_first("h3.list-items__item__title a")
    if title_link is None:
        return None
    title = title_link.text(strip=True)
    href = title_link.attributes.get("href", "")
    if not href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    # Portal ID
    portal_id = title_link.attributes.get("data-advert-id", "")
    if not portal_id:
        id_match = _ID_RE.search(href)
        if not id_match:
            return None
        portal_id = id_match.group(1)

    # Price
    price_raw = None
    price_el = card.css_first("strong.list-items__item__price")
    if price_el:
        price_raw = price_el.text(strip=True)

    # Location from tags
    location_raw = ""
    tag_spans = card.css("ul.in-tags li span")
    if tag_spans:
        location_raw = ", ".join(span.text(strip=True) for span in tag_spans if span.text(strip=True))

    # Area
    area_raw = None
    area_matches = _AREA_RE.findall(title)
    if area_matches:
        area_raw = area_matches[-1].strip() + " m2"

    # Image
    images = []
    img = card.css_first("figure img")
    if img:
        src = img.attributes.get("src", "")
        if src:
            if src.startswith("/"):
                src = BASE_URL + src
            images.append(src)

    return RawListing(
        portal="realityregio",
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
