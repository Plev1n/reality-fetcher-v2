"""iDNES Reality scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://reality.idnes.cz"

SEARCH_CONFIGS = {
    "dum": {
        "path": "/s/prodej/domy/rodinne/cena-do-10000000/okres-frydek-mistek/",
        "params": {"s-qc[groundAreaMin]": "750"},
    },
    "pozemek": {
        "path": "/s/prodej/pozemky/stavebni-pozemek/cena-do-10000000/okres-frydek-mistek/",
        "params": {"s-qc[groundAreaMin]": "750"},
    },
    "byt": {
        "path": "/s/prodej/byty/okres-frydek-mistek/",
        "params": {},
    },
}

PER_PAGE = 25
MAX_PAGES = 100

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")


@register("idnes")
class IdnesScraper(BaseScraper):
    """iDNES Reality scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        config = SEARCH_CONFIGS.get(listing_type)
        if not config:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(MAX_PAGES):
                url = BASE_URL + config["path"]
                params = dict(config["params"])
                if page > 0:
                    params["page"] = str(page)

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("div.c-products__inner")
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
    """Parse a single iDNES listing card."""
    title_node = card.css_first("h2.c-products__title")
    title = title_node.text(strip=True) if title_node else ""
    if not title:
        return None

    price_node = card.css_first("p.c-products__price")
    price_raw = price_node.text(strip=True) if price_node else None

    location_node = card.css_first("p.c-products__info")
    location_raw = location_node.text(strip=True) if location_node else ""

    link_node = card.css_first("a.c-products__link")
    href = link_node.attributes.get("href", "") if link_node else ""
    detail_url = href if href.startswith("http") else BASE_URL + href

    # Portal ID from URL
    portal_id = ""
    if href:
        segments = [s for s in href.rstrip("/").split("/") if s]
        if segments:
            portal_id = segments[-1]
    if not portal_id:
        return None

    # Image
    images = []
    img_node = card.css_first("img")
    if img_node:
        src = img_node.attributes.get("src", "") or img_node.attributes.get("data-src", "")
        if src:
            images.append(src)

    # Area from title
    area_raw = None
    area_matches = _AREA_RE.findall(title)
    if area_matches:
        area_raw = area_matches[-1].strip() + " m2"

    return RawListing(
        portal="idnes",
        portal_id=portal_id,
        title=title,
        url=detail_url,
        type_raw=title,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        images=images,
    )
