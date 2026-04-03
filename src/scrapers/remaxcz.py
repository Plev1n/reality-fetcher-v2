"""RE/MAX Czech (remax-czech.cz) scraper using HTML parsing with DMS GPS."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.remax-czech.cz"

SEARCH_CONFIGS = {
    "dum": "/reality/domy-a-vily/prodej/moravskoslezsky-kraj/",
    "pozemek": "/reality/pozemky/prodej/moravskoslezsky-kraj/",
    "byt": "/reality/byty/prodej/moravskoslezsky-kraj/",
}

PER_PAGE = 21
MAX_PAGES = 20

_AREA_RE = re.compile(r"(\d[\d\s\xa0]*)\s*m[²2]")
_ID_RE = re.compile(r"/reality/detail/(\d+)/")
_GPS_RE = re.compile(r"""(\d+)\xb0(\d+)'([\d.]+)"([NS]),\s*(\d+)\xb0(\d+)'([\d.]+)"([EW])""")


def _parse_gps(gps_str: str) -> tuple[float, float] | None:
    """Parse DMS GPS string like 49deg36'58.7"N,18deg19'56.4"E to (lat, lon)."""
    match = _GPS_RE.match(gps_str)
    if not match:
        return None
    lat_d, lat_m, lat_s = int(match.group(1)), int(match.group(2)), float(match.group(3))
    lon_d, lon_m, lon_s = int(match.group(5)), int(match.group(6)), float(match.group(7))
    lat = lat_d + lat_m / 60 + lat_s / 3600
    lon = lon_d + lon_m / 60 + lon_s / 3600
    if match.group(4) == "S":
        lat = -lat
    if match.group(8) == "W":
        lon = -lon
    return (lat, lon)


@register("remaxcz")
class RemaxczScraper(BaseScraper):
    """remax-czech.cz scraper via HTML data attributes."""

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
                    params["stranka"] = str(page)

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("div.pl-items__item")
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
    """Parse a div.pl-items__item card using data attributes."""
    data_url = card.attributes.get("data-url", "")
    data_title = card.attributes.get("data-title", "")
    data_price = card.attributes.get("data-price", "")
    data_img = card.attributes.get("data-img", "")
    data_gps = card.attributes.get("data-gps", "")
    data_address = card.attributes.get("data-display-address", "")

    if not data_url or not data_title:
        return None

    id_match = _ID_RE.search(data_url)
    if not id_match:
        return None
    portal_id = id_match.group(1)

    url = BASE_URL + data_url if data_url.startswith("/") else data_url

    # Price
    price_raw = None
    if data_price:
        price_text = re.sub(r"<[^>]+>", "", data_price)
        price_text = price_text.replace("\xa0", " ").replace("&nbsp;", " ").strip()
        if "Kc" in price_text or "Kč" in price_text:
            price_raw = price_text.split("Kč")[0].strip() + " Kč" if "Kč" in price_text else price_text

    # Area
    area_raw = None
    area_match = _AREA_RE.search(data_title)
    if area_match:
        area_raw = area_match.group(1).replace("\xa0", " ").strip() + " m2"

    # GPS
    coords = _parse_gps(data_gps) if data_gps else None

    images = [data_img] if data_img else []

    return RawListing(
        portal="remaxcz",
        portal_id=portal_id,
        title=data_title,
        url=url,
        type_raw=data_title,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=data_address,
        address_raw=data_address or None,
        coordinates=coords,
        images=images,
    )
