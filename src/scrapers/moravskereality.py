"""SeveroMoravske Reality scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://severo.moravskereality.cz"

SEARCH_CONFIGS = {
    "dum": "/frydek-mistek/prodej/rodinne-domy/",
    "pozemek": "/frydek-mistek/prodej/pozemky/",
    "byt": "/frydek-mistek/prodej/byty/",
}

PER_PAGE = 20
MAX_PAGES = 50

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")
_ID_RE = re.compile(r"-(\d+)\.html")


@register("moravskereality")
class MoravskerealityScraper(BaseScraper):
    """severo.moravskereality.cz scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + path
                params = {"sff": "1"}
                if page > 1:
                    params["strana"] = str(page)

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("article.i-estate")
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
    """Parse an article.i-estate card."""
    title_link = card.css_first("h2.i-estate__header-title a") or card.css_first("a.i-estate__title-link")
    if title_link is None:
        return None

    title = title_link.text(strip=True)
    href = title_link.attributes.get("href", "")
    if not href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    id_match = _ID_RE.search(href)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    # Price
    price_raw = None
    price_el = card.css_first("h3.i-estate__footer-price-value")
    if price_el:
        price_raw = price_el.text(strip=True)

    # Location from title (after area m2)
    location_raw = ""
    area_match = _AREA_RE.search(title)
    if area_match:
        after_area = title[area_match.end():].strip()
        if after_area:
            location_raw = after_area
    if not location_raw:
        parts = href.split("/")
        for i, p in enumerate(parts):
            if p in ("rodinne-domy", "pozemky", "chaty", "chalupy", "vily") and i + 1 < len(parts):
                location_raw = parts[i + 1].replace("-", " ").title()
                break

    # Area
    area_raw = None
    area_matches = _AREA_RE.findall(title)
    if area_matches:
        area_raw = area_matches[-1].strip() + " m2"

    # Image
    images = []
    img = card.css_first("img[alt]")
    if img:
        src = img.attributes.get("src", "")
        if src and "32x32" not in src:
            images.append(src)
        else:
            source = card.css_first("source[type='image/jpeg']")
            if source:
                srcset = source.attributes.get("srcset", "")
                if srcset:
                    images.append(srcset.split(" ")[0])

    return RawListing(
        portal="moravskereality",
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
