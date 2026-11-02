"""Municipal infrastructure: sewer/ČOV public tenders from TED (EU tenders journal)."""

from __future__ import annotations

import re

import httpx

TED_URL = "https://api.ted.europa.eu/v3/notices/search"

NOTICE_TYPES = {
    "cn-standard": "oznámení o zahájení zakázky (výběr zhotovitele)",
    "can-standard": "oznámení o zadání zakázky (smlouva uzavřena)",
    "pin-only": "předběžné oznámení (plán)",
    "can-modif": "změna smlouvy",
}


def _ces(value) -> str | None:
    if isinstance(value, dict):
        v = value.get("ces") or next(iter(value.values()), None)
        return v[0] if isinstance(v, list) else v
    return value


_RELEVANT = re.compile(r"kanaliz|čov\b|čistír|odpadní\w* vod|splašk", re.IGNORECASE)


def parse_ted(data: dict) -> list[dict]:
    out = []
    for n in data.get("notices") or []:
        if not _RELEVANT.search(_ces(n.get("notice-title")) or ""):
            continue
        pid = n.get("publication-number")
        ntype = n.get("notice-type") or ""
        out.append({
            "id": pid,
            "date": (n.get("publication-date") or "")[:10],
            "title": _ces(n.get("notice-title")),
            "type": NOTICE_TYPES.get(ntype, ntype),
            "buyer": _ces(n.get("buyer-name")),
            "url": f"https://ted.europa.eu/cs/notice/-/detail/{pid}",
        })
    return sorted(out, key=lambda x: x["date"])


async def sewer_tenders(municipality: str, client: httpx.AsyncClient) -> list[dict]:
    resp = await client.post(TED_URL, json={
        "query": f'FT="{municipality}" AND (FT=kanalizace OR FT=ČOV)',
        "fields": ["publication-number", "notice-title", "publication-date", "buyer-name", "notice-type"],
        "limit": 20,
    })
    resp.raise_for_status()
    return parse_ted(resp.json())
