"""Eurobydleni.cz scraper using HTML parsing."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.eurobydleni.cz"

SEARCH_CONFIGS = {
    "dum": "/domy/frydek-mistek/prodej/",
    "pozemek": "/pozemky/frydek-mistek/prodej/",
    "byt": "/byty/frydek-mistek/prodej/",
}

PER_PAGE = 12
MAX_PAGES = 30

_AREA_RE = re.compile(r"([\d\s\xa0,.]+)\s*m[²2]")
_ID_RE = re.compile(r"/detail/(\d+)/")
_PRICE_ON_REQUEST = 999999999


@register("eurobydleni")
class EurobydleniScraper(BaseScraper):
    """eurobydleni.cz scraper via HTML parsing."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        path = SEARCH_CONFIGS.get(listing_type)
        if not path:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + path
                if page > 1:
                    url += f"page-{page}/"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except Exception:
                    break

                tree = HTMLParser(resp.text)
                cards = tree.css("li.list-items__item")
                if not cards:
                    break

                for card in cards:
                    raw = _parse_card(card, listing_type)
                    if raw is not None:
                        results.append(raw)

                # Check pagination max
                pag = tree.css_first("ul.list-pagination")
                if pag:
                    try:
                        max_page = int(pag.attributes.get("data-max-page", "1"))
                    except ValueError:
                        max_page = 1
                    if page >= max_page:
                        break
                elif len(cards) < PER_PAGE:
                    break

                await self._delay()

        return results


def _parse_card(card, listing_type: str) -> RawListing | None:
    """Parse a li.list-items__item card."""
    title_el = card.css_first("h2.list-items__item__title a")
    if title_el is None:
        return None
    title = title_el.attributes.get("title", "") or title_el.text(strip=True)
    href = title_el.attributes.get("href", "")
    if not href:
        return None
    url = BASE_URL + href if href.startswith("/") else href

    # Portal ID
    id_match = _ID_RE.search(href)
    if id_match:
        portal_id = id_match.group(1)
    else:
        contact_el = card.css_first("a[data-advert-id]")
        if contact_el:
            portal_id = contact_el.attributes.get("data-advert-id", "")
        else:
            return None
    if not portal_id:
        return None

    # Price from structured data
    price_raw = None
    price_meta = card.css_first("meta[itemprop='price']")
    if price_meta:
        price_val = price_meta.attributes.get("content", "")
        try:
            price_int = int(price_val)
            if price_int != _PRICE_ON_REQUEST:
                price_raw = str(price_int)
        except (ValueError, TypeError):
            pass
    if price_raw is None:
        price_li = card.css_first("div.list-items__content li")
        if price_li:
            price_text = price_li.text(strip=True)
            if "Kc" in price_text or "Kč" in price_text:
                price_raw = price_text

    # Location
    location_raw = ""
    content_items = card.css("div.list-items__content__in li")
    if len(content_items) >= 2:
        location_raw = content_items[1].text(strip=True)

    # Area from footer tags
    area_raw = None
    for tag in card.css("div.list-items__content__footer span"):
        tag_text = tag.text(strip=True)
        if "pozemek:" in tag_text.lower():
            area_match = _AREA_RE.search(tag_text)
            if area_match:
                area_raw = area_match.group(1).replace(",", ".").strip() + " m2"
                break
        elif "m2" in tag_text.lower() or "m²" in tag_text.lower():
            area_match = _AREA_RE.search(tag_text)
            if area_match:
                area_raw = area_match.group(1).replace(",", ".").strip() + " m2"
    if not area_raw:
        area_match = _AREA_RE.search(title)
        if area_match:
            area_raw = area_match.group(1).replace(",", ".").strip() + " m2"

    # Image
    images = []
    img = card.css_first("figure img")
    if img:
        src = img.attributes.get("src", "")
        if src:
            images.append(src)

    return RawListing(
        portal="eurobydleni",
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
