"""Fetch and parse listing detail pages into structured ListingDetails."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, fields
from datetime import date

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser


@dataclass
class ListingDetails:
    url: str
    fetched: str
    ok: bool = True
    title: str | None = None
    price: int | None = None
    location: str | None = None
    usable_area: int | None = None
    plot_area: int | None = None
    built_area: int | None = None
    rooms: int | None = None
    disposition: str | None = None
    year_built: int | None = None
    condition: str | None = None
    construction: str | None = None
    heating: str | None = None
    sewer: str | None = None
    gas: bool | None = None
    penb: str | None = None
    agency: str | None = None
    agent: str | None = None
    ref_number: str | None = None
    listed_since: str | None = None
    old_price: int | None = None
    description: str | None = None


def details_to_dict(d: ListingDetails) -> dict:
    return asdict(d)


def details_from_dict(x: dict) -> ListingDetails:
    known = {f.name for f in fields(ListingDetails)}
    return ListingDetails(**{k: v for k, v in x.items() if k in known})


# --- text helpers ---

# thousands separated by space or dot ("1 375", "1.250"); not glued to "5+1 140"
_NUM = r"(?<![\d+.])(\d{1,3}(?:[ .]\d{3})+|\d+)"
MIN_AREA = 20
_UNIT = r"\s*(?:\(m[²2]\))?"


def _clean(text: str) -> str:
    text = text.replace("‍", "").replace("\xa0", " ").replace(" ", " ")
    return re.sub(r"[ \t]+", " ", text)


def _int(s: str | None) -> int | None:
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    return int(digits) if digits else None


def _area(v: int | None) -> int | None:
    return v if v is not None and v >= MIN_AREA else None


def _first_num(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(_NUM, _clean(s))
    return _int(m.group(1)) if m else None


def _dl_pairs(tree: HTMLParser) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for dt in tree.css("dt"):
        key = " ".join(dt.text(separator=" ").split()).rstrip(":").lower()
        node = dt.next
        while node is not None and node.tag != "dd":
            if node.tag == "dt":
                node = None
                break
            node = node.next
        if node is not None and key and key not in pairs:
            pairs[key] = " ".join(_clean(node.text(separator=" ")).split())
    return pairs


def _pick(pairs: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        if k in pairs and pairs[k]:
            return pairs[k]
    return None


def _search(pattern: str, text: str, group: int = 1) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(group).strip() if m else None


_DESC_SELECTOR = "div.b-desc, div.popisdetail, [itemprop=description]"

_CONDITIONS = [
    "před rekonstrukcí", "po rekonstrukci", "v rekonstrukci", "novostavba",
    "k demolici", "velmi dobrý stav", "dobrý stav", "špatný stav", "ve výstavbě",
]


def _sewer_from_text(text: str) -> str | None:
    low = text.lower()
    if re.search(r"septik|jímk|žump", low):
        return "septik / jímka"
    # "kanalizace" counts only if it's an existing connection, not a plan
    for m in re.finditer(r"kanalizac\w*", low):
        ctx = low[max(0, m.start() - 60):m.end() + 100]
        if not re.search(r"plánovan|připravuj|výhledově|budouc|bude", ctx):
            return "veřejná kanalizace"
    return None


def parse_details(html: str, url: str) -> ListingDetails:
    """Parse an HTML detail page (iDNES, Bazoš, Realingo, others) using dt/dd pairs, text and title."""
    d = ListingDetails(url=url, fetched=date.today().isoformat())
    if not html or not html.strip():
        d.ok = False
        return d

    agency = _search(r'"listing_brand"\s*:\s*"([^"]+)"', html)
    price = _int(_search(r'"listing_price"\s*:\s*(\d+)', html))
    tree = HTMLParser(html)
    pairs = _dl_pairs(tree)
    h1 = tree.css_first("h1")
    title = " ".join(_clean(h1.text(separator=" ")).split()) if h1 else None
    for node in tree.css("script, style, noscript"):
        node.decompose()
    # Prefer the listing's own description: portals append other listings to the page
    desc = tree.css_first(_DESC_SELECTOR)
    body = desc or tree.body
    text = _clean(body.text(separator="\n")) if body else ""
    if not text.strip():
        d.ok = False
        return d

    d.title = title
    d.agency = agency
    d.price = price or _first_num(_pick(pairs, "cena", "celková cena"))
    info = tree.css_first("p.b-detail__info")
    d.location = " ".join(info.text(separator=" ").split()) if info else None
    d.ref_number = _pick(pairs, "číslo zakázky", "id zakázky", "číslo inzerátu")

    d.usable_area = _area(_first_num(_pick(pairs, "užitná plocha")) or _int(
        _search(r"užitn\w* ploch\w*" + _UNIT + r"[^\d\n]{0,20}" + _NUM, text)))
    d.plot_area = _area(_first_num(_pick(pairs, "plocha pozemku")) or _int(
        _search(r"plocha (?:parcely|pozemku)" + _UNIT + r"[^\d\n]{0,20}" + _NUM, text)))
    d.built_area = _area(_first_num(_pick(pairs, "zastavěná plocha")) or _int(
        _search(r"zastavěn\w* ploch\w*" + _UNIT + r"[^\d\n]{0,20}" + _NUM, text)))

    if title and (d.usable_area is None or d.plot_area is None):
        m = re.search(_NUM + r"\s*m[²2]?,?\s*(?:s pozemkem|pozemek)\s*" + _NUM, _clean(title), re.IGNORECASE)
        if m:
            d.usable_area = d.usable_area or _area(_int(m.group(1)))
            d.plot_area = d.plot_area or _area(_int(m.group(2)))

    disp = re.search(r"\b([1-9])\s*\+\s*(kk|1)\b", (title or "") + "\n" + text, re.IGNORECASE)
    if disp:
        d.disposition = f"{disp.group(1)}+{disp.group(2).lower()}"
        d.rooms = int(disp.group(1))

    year = _pick(pairs, "kolaudace", "rok kolaudace", "rok výstavby")
    d.year_built = _int(_search(r"((?:18|19|20)\d\d)", year or "")) or _int(
        _search(r"(?:kolaudac\w*|rok\w* výstavby|postaven\w*)[^\d\n]{0,15}((?:18|19|20)\d\d)", text))

    cond = _pick(pairs, "stav budovy", "stav objektu", "stav")
    if cond:
        d.condition = cond.lower()
    else:
        low = text.lower()
        d.condition = next((c for c in _CONDITIONS if c in low), None)

    constr = _pick(pairs, "konstrukce budovy", "stavba", "konstrukce")
    d.construction = constr.lower() if constr else None

    heat = _pick(pairs, "topení", "vytápění")
    d.heating = (heat or _search(r"vytápění\s*:\s*([^\n.]{3,160})", text)
                 or _search(r"vytápěn\w*\s+([^\n.]{3,160})", text))

    odpad = _pick(pairs, "odpad", "kanalizace")
    d.sewer = odpad or _sewer_from_text(text)

    gas = _pick(pairs, "plyn")
    if gas:
        d.gas = not re.search(r"\bne\b|bez", gas.lower())
    else:
        for m in re.finditer(r"\bplyn\b|plynov", text, re.IGNORECASE):
            ctx = text[max(0, m.start() - 25):m.end() + 25].lower()
            if re.search(r"není|nezaveden|\bbez\b|chybí|\bne\b", ctx):
                d.gas = False
                break
            d.gas = True
            break

    penb = _pick(pairs, "penb", "energetická náročnost budovy", "energetická náročnost")
    # case-sensitive: the Czech word "a" must not read as class A
    m = re.search(r"\b([A-G])\b", penb or "") or re.search(r"PENB[^A-G\n]{0,20}\b([A-G])\b", text)
    d.penb = m.group(1) if m else None

    if desc:
        d.description = " ".join(_clean(desc.text(separator=" ")).split())[:4000]
    return d


def _names(items) -> str | None:
    names = [i.get("name", "").lower() for i in (items or []) if isinstance(i, dict) and i.get("name")]
    return ", ".join(names) or None


def parse_sreality_detail(result: dict, url: str) -> ListingDetails:
    """Parse the Sreality api/v1/estates/{id} 'result' object."""
    d = ListingDetails(url=url, fetched=date.today().isoformat())
    d.title = result.get("advert_name")
    price = result.get("price_summary_czk") or result.get("price_czk")
    d.price = int(price) if price and price > 1 else None
    loc = result.get("locality") or {}
    city, part = loc.get("city"), loc.get("citypart")
    d.location = (f"{city} - {part}" if part and part != city else city) or None
    d.usable_area = result.get("usable_area") or result.get("floor_area")
    d.plot_area = result.get("estate_area")
    d.built_area = result.get("building_area")
    room = result.get("room_count_cb") or {}
    d.rooms = room.get("value") or None
    disp = re.search(r"\b([1-9])\s*\+\s*(kk|1)\b", d.title or "", re.IGNORECASE)
    if disp:
        d.disposition = f"{disp.group(1)}+{disp.group(2).lower()}"
        d.rooms = int(disp.group(1))
    d.year_built = result.get("acceptance_year") or None
    cond = (result.get("building_condition") or {}).get("name")
    d.condition = cond.lower() if cond and not cond.startswith("-") else None
    constr = (result.get("building_type") or {}).get("name")
    d.construction = constr.lower() if constr and not constr.startswith("-") else None
    d.heating = _names(result.get("heating_source_set")) or _names(result.get("heating_set"))
    d.sewer = _names(result.get("gully_set"))
    d.gas = bool(result.get("gas_set"))
    penb = (result.get("energy_efficiency_rating_cb") or {}).get("name") or ""
    d.penb = _search(r"^([A-G])\b", penb)
    d.ref_number = result.get("advert_code") or None
    d.listed_since = result.get("since") or None
    old = result.get("price_summary_old_czk")
    d.old_price = int(old) if old else None
    user = result.get("user") or {}
    d.agent = user.get("user_name") or None
    desc = result.get("advert_description")
    d.description = desc[:4000] if desc else None
    return d


_SREALITY_ID = re.compile(r"sreality\.cz/detail/.*/(\d+)/?$")


async def fetch_details(url: str, client: httpx.AsyncClient) -> ListingDetails:
    """Fetch one listing detail. Never raises; returns ok=False on failure."""
    try:
        m = _SREALITY_ID.search(url)
        if m:
            resp = await client.get(f"https://www.sreality.cz/api/v1/estates/{m.group(1)}")
            resp.raise_for_status()
            return parse_sreality_detail(resp.json().get("result") or {}, url)
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_details(resp.text, url)
    except Exception:
        return ListingDetails(url=url, fetched=date.today().isoformat(), ok=False)
