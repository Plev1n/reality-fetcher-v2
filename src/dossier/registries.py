"""Public registries: ARES (business register) and ISIR (insolvency register).

Only data relevant to a purchase is kept; birth numbers and street addresses from ISIR are dropped.
"""

from __future__ import annotations

import re

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

ARES_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/vyhledat"
ISIR_URL = "https://isir.justice.cz/isir/ueu/vysledek_lustrace.do"


def split_name(owner: str) -> tuple[str, str]:
    """Cadastre lists 'Příjmení Jméno'. Returns (surname, first name)."""
    parts = owner.split()
    return (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (owner, "")


def parse_ares(data: dict) -> list[dict]:
    return [{
        "ico": s.get("ico"),
        "name": s.get("obchodniJmeno"),
        "address": (s.get("sidlo") or {}).get("textovaAdresa"),
        "since": s.get("datumVzniku"),
        "until": s.get("datumZaniku"),
    } for s in data.get("ekonomickeSubjekty") or []]


async def ares_lookup(owner: str, client: httpx.AsyncClient) -> list[dict]:
    surname, first = split_name(owner)
    resp = await client.post(ARES_URL, json={"obchodniJmeno": f"{first} {surname}".strip(), "pocet": 20})
    resp.raise_for_status()
    return parse_ares(resp.json())


def parse_isir(html: str) -> list[dict]:
    tree = HTMLParser(html)
    text = " ".join((tree.body.text(separator=" ") if tree.body else "").split())
    m = re.search(r"POČET NALEZENÝCH DLUŽNÍKŮ\s*(\d+)", text)
    if not m or m.group(1) == "0":
        return []
    # Rows are <th>label</th><td><b><span>value</span></b>…</td>; one record starts at "Spisová značka"
    records, current = [], {}
    for tr in tree.css("tr"):
        th, td = tr.css_first("th"), tr.css_first("td")
        if th is None or td is None:
            continue
        key = " ".join(th.text(separator=" ").split()).rstrip(":").strip()
        span = td.css_first("span")
        val = " ".join((span or td).text(separator=" ").split())
        if key.startswith("Spisová značka") and current:
            records.append(current)
            current = {}
        current[key] = val
    if current:
        records.append(current)
    out = []
    for r in (r for r in records if r.get("Spisová značka")):
        birth = re.search(r"\b(?:\d{1,2}\.){2}((?:19|20)\d\d)\b", r.get("Rodné číslo / Datum nar.", ""))
        out.append({
            "name": r.get("Jméno/název"),
            "case": r.get("Spisová značka"),
            "birth_year": birth.group(1) if birth else None,
            "city": (r.get("Bydliště") or "").split(",")[0].strip() or None,
            "state": r.get("Stav řízení"),
        })
    return out


async def isir_lookup(owner: str, client: httpx.AsyncClient) -> list[dict]:
    surname, first = split_name(owner)
    resp = await client.get(ISIR_URL, params={
        "nazev_osoby": surname, "jmeno_osoby": first,
        "aktualnost": "AKTUALNI_I_UKONCENA", "rowsAtOnce": "50",
    })
    resp.raise_for_status()
    return parse_isir(resp.text)
