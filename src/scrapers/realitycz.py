"""Reality.cz scraper using HTML parsing with GPS in CSS class names."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.reality.cz"

SEARCH_CONFIGS = {
    "dum": "/prodej/domy/moravskoslezsky-kraj/frydek-mistek/",
    "pozemek": "/prodej/pozemky/moravskoslezsky-kraj/frydek-mistek/",
    "byt": "/prodej/byty/moravskoslezsky-kraj/frydek-mistek/",
}

PER_PAGE = 25
MAX_PAGES = 20

_AREA_RE = re.compile(r"([\d\s\xa0.,]+)\s*m[²2]")
_GPS_RE = re.compile(r"gpsx([\d.]+)")
_GPSY_RE = re.compile(r"gpsy([\d.]+)")
_ID_RE = re.compile(r"/([A-Z0-9]+-[A-Z0-9]+)/")


@register("realitycz")
class RealityczScraper(BaseScraper):
    """reality.cz scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        total_count = None
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + path
                params = {}
                if page > 1 and total_count is not None:
                    params["g"] = f"{page - 1}-0-{total_count}"

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("div.xvypis")
                if not cards:
                    break

                # Extract total count on first page
                if page == 1 and total_count is None:
                    meta_desc = tree.css_first("meta[name='description']")
                    if meta_desc:
                        desc_text = meta_desc.attributes.get("content", "")
                        count_match = re.search(r"(\d+)\s+nabídek", desc_text)
                        if count_match:
                            total_count = int(count_match.group(1))

                for card in cards:
                    raw = _parse_card(card, listing_type)
                    if raw is not None:
                        results.append(raw)

                if len(cards) < PER_PAGE:
                    break
                await self._delay()

        return results


def _parse_card(card, listing_type: str) -> RawListing | None:
    """Parse a div.xvypis card."""
    title_el = card.css_first("p.vypisnaz a")
    if title_el is None:
        return None
    title = title_el.text(strip=True)
    href = title_el.attributes.get("href", "")
    if not href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    id_match = _ID_RE.search(href)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    # Price
    price_raw = None
    price_el = card.css_first("p.vypiscena span strong")
    if price_el:
        price_raw = price_el.text(strip=True)

    # Area from p.lokalita
    area_raw = None
    location_raw = ""
    area_el = card.css_first("p.lokalita")
    if area_el:
        area_text = area_el.text(strip=True)
        area_matches = _AREA_RE.findall(area_text)
        if area_matches:
            raw_val = area_matches[-1].replace("\xa0", " ").replace(".", "").strip()
            area_raw = raw_val + " m2"

    # Location from title (after last comma)
    if "," in title:
        location_raw = title.rsplit(",", 1)[-1].strip()

    # GPS from CSS classes
    coords = None
    css_classes = card.attributes.get("class", "")
    lat_match = _GPS_RE.search(css_classes)
    lon_match = _GPSY_RE.search(css_classes)
    if lat_match and lon_match:
        try:
            lat = float(lat_match.group(1))
            lon = float(lon_match.group(1))
            if lat > 0 and lon > 0:
                coords = (lat, lon)
        except ValueError:
            pass

    # Image
    images = []
    img = card.css_first("div.thumbnail img")
    if img:
        src = img.attributes.get("src", "")
        if src:
            if src.startswith("/"):
                src = BASE_URL + src
            images.append(src)

    return RawListing(
        portal="realitycz",
        portal_id=portal_id,
        title=title,
        url=url,
        type_raw=title,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        coordinates=coords,
        images=images,
    )
