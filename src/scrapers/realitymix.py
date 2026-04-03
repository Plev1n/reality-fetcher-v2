"""RealityMix.cz scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://realitymix.cz/vypis-nabidek/"

SEARCH_CONFIGS = {
    "dum": {
        "form[inzerat_typ]": "1",
        "form[nemovitost_typ][]": "6",
        "form[adresa_kraj_id][]": "132",
        "form[adresa_region_id][132][]": "3802",
        "form[cena_normalizovana__to]": "10000000",
        "form[plocha__from]": "750",
    },
    "pozemek": {
        "form[inzerat_typ]": "1",
        "form[nemovitost_typ][]": "3",
        "form[adresa_kraj_id][]": "132",
        "form[adresa_region_id][132][]": "3802",
        "form[cena_normalizovana__to]": "10000000",
        "form[plocha__from]": "750",
    },
    "byt": {
        "form[inzerat_typ]": "1",
        "form[nemovitost_typ][]": "2",
        "form[adresa_kraj_id][]": "132",
        "form[adresa_region_id][132][]": "3802",
        "form[cena_normalizovana__to]": "10000000",
    },
}

PER_PAGE = 20
MAX_PAGES = 50

_AREA_RE = re.compile(r"([\d\s\xa0]+)\s*m[²2]")


@register("realitymix")
class RealitymixScraper(BaseScraper):
    """RealityMix.cz scraper via HTML listing pages."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        config = SEARCH_CONFIGS.get(listing_type)
        if not config:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                params = {**config}
                if page > 1:
                    params["stranka"] = str(page)

                try:
                    resp = await client.get(BASE_URL, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("li.advert-item")
                if not cards:
                    break

                for card in cards:
                    raw = _parse_card(card, listing_type)
                    if raw is not None:
                        results.append(raw)

                if len(cards) < PER_PAGE or page >= MAX_PAGES:
                    break
                await self._delay()

        return results


def _parse_card(card, listing_type: str) -> RawListing | None:
    """Parse a single RealityMix listing card."""
    # Detail link
    url = ""
    portal_id = ""
    for a_el in card.css("a"):
        href = a_el.attributes.get("href", "")
        if "/detail/" in href:
            if href.startswith("//"):
                url = "https:" + href
            elif href.startswith("/"):
                url = "https://realitymix.cz" + href
            elif not href.startswith("http"):
                url = "https://" + href
            else:
                url = href
            id_match = re.search(r"-(\d+)\.html", href)
            if id_match:
                portal_id = id_match.group(1)
            break

    if not portal_id:
        portal_id = card.attributes.get("data-id", "")
    if not portal_id:
        return None

    # Title
    h2 = card.css_first("h2")
    title = h2.text(strip=True) if h2 else ""

    # Price
    price_el = card.css_first("div.text-xl")
    price_raw = price_el.text(strip=True) if price_el else None

    # Location
    location_raw = ""
    for p_el in card.css("p"):
        txt = p_el.text(strip=True)
        if not txt or len(txt) < 3:
            continue
        if "Kč" in txt or "líbí" in txt.lower() or txt.startswith("+") or txt.isdigit():
            continue
        if "okr." in txt or "okres" in txt.lower():
            location_raw = txt
            break
        if not location_raw and not txt[0].isdigit():
            location_raw = txt

    # Image
    images = []
    img_el = card.css_first("img")
    if img_el:
        src = img_el.attributes.get("src", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            images.append(src)

    # Area from title
    area_raw = None
    area_matches = _AREA_RE.findall(title)
    if area_matches:
        area_raw = area_matches[-1].strip() + " m2"

    return RawListing(
        portal="realitymix",
        portal_id=str(portal_id),
        title=title,
        url=url,
        type_raw=title,
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        images=images,
    )
