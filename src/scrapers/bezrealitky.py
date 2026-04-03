"""Bezrealitky.cz scraper using __NEXT_DATA__ extraction."""

from __future__ import annotations

import json
import re

from src.scrapers import register
from src.scrapers.base import BaseScraper
from src.models import RawListing

BASE_URL = "https://www.bezrealitky.cz"

SEARCH_CONFIGS = {
    "dum": {
        "path": "/vypis/nabidka-prodej/dum/moravskoslezsky-kraj",
        "params": {"priceTo": "10000000"},
    },
    "pozemek": {
        "path": "/vypis/nabidka-prodej/pozemek/moravskoslezsky-kraj",
        "params": {
            "priceTo": "10000000",
            "surfaceLandFrom": "750",
            "landType": "STAVEBNI",
        },
    },
    "byt": {
        "path": "/vypis/nabidka-prodej/byt/moravskoslezsky-kraj",
        "params": {"priceTo": "10000000"},
    },
}

PER_PAGE = 15
MAX_PAGES = 100

_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*(.*?)\s*</script>',
    re.DOTALL,
)


@register("bezrealitky")
class BezrealitkyScraper(BaseScraper):
    """Bezrealitky.cz scraper via __NEXT_DATA__ HTML extraction."""

    async def scrape(self, listing_type: str) -> list[RawListing]:
        config = SEARCH_CONFIGS.get(listing_type)
        if not config:
            return []

        results: list[RawListing] = []
        async with self._get_client() as client:
            for page in range(1, MAX_PAGES + 1):
                url = BASE_URL + config["path"]
                params = {**config["params"], "page": str(page)}

                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except Exception:
                    break

                adverts = _extract_adverts(resp.text)
                if not adverts:
                    break

                for advert in adverts:
                    raw = _parse_advert(advert, listing_type)
                    if raw is not None:
                        results.append(raw)

                if len(adverts) < PER_PAGE or page >= MAX_PAGES:
                    break
                await self._delay()

        return results


def _get_apollo_field(obj: dict, field: str) -> object:
    """Get a field from an Apollo cache object, handling parametrized keys."""
    if field in obj:
        return obj[field]
    prefix = field + "("
    for key in obj:
        if key.startswith(prefix):
            return obj[key]
    return None


def _resolve_apollo_advert(advert: dict, cache: dict) -> dict:
    """Resolve an Apollo cache advert into a flat dict."""
    resolved: dict = {}
    for field in ("id", "uri", "estateType", "offerType", "surface",
                  "surfaceLand", "price", "currency", "gps", "__typename"):
        resolved[field] = advert.get(field)

    resolved["address"] = _get_apollo_field(advert, "address") or ""
    resolved["name"] = _get_apollo_field(advert, "imageAltText") or ""
    resolved["description"] = _get_apollo_field(advert, "description") or ""

    # Resolve main image
    main_img = advert.get("mainImage")
    if isinstance(main_img, dict) and "__ref" in main_img:
        img_obj = cache.get(main_img["__ref"], {})
        resolved["mainImage"] = _get_apollo_field(img_obj, "url") or ""
    elif isinstance(main_img, str):
        resolved["mainImage"] = main_img

    # Resolve public images
    pub_imgs = _get_apollo_field(advert, "publicImages") or []
    resolved_imgs = []
    if isinstance(pub_imgs, list):
        for img_ref in pub_imgs[:10]:
            if isinstance(img_ref, dict) and "__ref" in img_ref:
                img_obj = cache.get(img_ref["__ref"], {})
                img_url = _get_apollo_field(img_obj, "url") or ""
                if img_url:
                    resolved_imgs.append(img_url)
            elif isinstance(img_ref, str):
                resolved_imgs.append(img_ref)
    resolved["publicImages"] = resolved_imgs

    return resolved


def _extract_adverts(html: str) -> list[dict]:
    """Extract advert objects from __NEXT_DATA__ JSON."""
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return []

    try:
        next_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    page_props = next_data.get("props", {}).get("pageProps", {})

    # Strategy 1: Direct adverts list
    adverts = page_props.get("adverts") or page_props.get("listings")
    if isinstance(adverts, list) and adverts:
        return adverts

    # Strategy 2: Nested data key
    for key in ("data", "searchResult", "result"):
        container = page_props.get(key, {})
        if isinstance(container, dict):
            for sub_key in ("adverts", "listings", "list", "items"):
                items = container.get(sub_key)
                if isinstance(items, list) and items:
                    return items

    # Strategy 3: Apollo cache
    apollo_state = (
        page_props.get("__APOLLO_STATE__")
        or page_props.get("apolloCache")
        or page_props.get("apolloState")
        or page_props.get("initialApolloState")
    )
    if isinstance(apollo_state, dict):
        adverts = []
        for key, value in apollo_state.items():
            if not isinstance(value, dict):
                continue
            typename = value.get("__typename", "")
            if typename in ("Advert", "AdvertListing", "Estate", "Property"):
                resolved = _resolve_apollo_advert(value, apollo_state)
                adverts.append(resolved)
        if adverts:
            return adverts

    return []


def _parse_advert(advert: dict, listing_type: str) -> RawListing | None:
    """Parse a single advert dict into a RawListing."""
    portal_id = str(advert.get("id") or advert.get("uri") or "")
    if not portal_id:
        return None

    uri = advert.get("uri", "")
    title = advert.get("name") or advert.get("title") or ""

    # Address
    address = advert.get("address") or ""
    if isinstance(address, dict):
        parts = [address.get("street", ""), address.get("city", ""), address.get("district", "")]
        location_raw = ", ".join(p for p in parts if p)
    else:
        location_raw = str(address)

    # Price
    price = advert.get("price")
    if isinstance(price, (int, float)) and price > 0:
        price_raw = f"{int(price)} Kc"
    else:
        price_raw = None

    # Areas
    surface = advert.get("surface")
    surface_land = advert.get("surfaceLand")

    area_raw = None
    if isinstance(surface_land, (int, float)) and surface_land > 0:
        area_raw = f"{int(surface_land)} m2"
    elif isinstance(surface, (int, float)) and surface > 0:
        area_raw = f"{int(surface)} m2"

    # GPS
    coords = None
    gps = advert.get("gps")
    if isinstance(gps, dict):
        lat = gps.get("lat")
        lng = gps.get("lng") or gps.get("lon")
        if lat is not None and lng is not None:
            coords = (float(lat), float(lng))

    # Images
    images = []
    public_images = advert.get("publicImages") or advert.get("images") or []
    if isinstance(public_images, list):
        for img in public_images[:10]:
            if isinstance(img, str):
                images.append(img)
            elif isinstance(img, dict):
                img_url = img.get("url") or img.get("src") or ""
                if img_url:
                    images.append(img_url)
    if not images:
        main_image = advert.get("mainImage") or advert.get("mainImageUrl")
        if isinstance(main_image, str) and main_image:
            images.append(main_image)

    # Description
    description = advert.get("description") or advert.get("text") or ""

    # URL
    if uri:
        detail_url = f"{BASE_URL}/nemovitosti-byty-domy/{uri}"
    else:
        detail_url = f"{BASE_URL}/nemovitosti-byty-domy/{portal_id}"

    return RawListing(
        portal="bezrealitky",
        portal_id=portal_id,
        title=title,
        url=detail_url,
        type_raw=advert.get("type") or advert.get("offerType") or title or "",
        price_raw=price_raw,
        area_raw=area_raw,
        location_raw=location_raw,
        address_raw=location_raw or None,
        description=description,
        coordinates=coords,
        images=images,
    )
