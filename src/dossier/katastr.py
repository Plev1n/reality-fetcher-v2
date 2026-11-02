"""Cadastre helpers: parcel areas from ČÚZK INSPIRE WFS and interpretation of LV restrictions."""

from __future__ import annotations

import re
from html import escape

import httpx

WFS_URL = "https://services.cuzk.cz/wfs/inspire-cp-wfs.asp"


def wfs_filter(ku_code: int, parcels: list[str]) -> str:
    conds = "".join(
        "<fes:PropertyIsEqualTo><fes:ValueReference>CP:nationalCadastralReference</fes:ValueReference>"
        f"<fes:Literal>{ku_code}-{escape(p)}</fes:Literal></fes:PropertyIsEqualTo>"
        for p in parcels
    )
    if len(parcels) > 1:
        conds = f"<fes:Or>{conds}</fes:Or>"
    return f'<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0">{conds}</fes:Filter>'


def parse_wfs_areas(xml: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for feat in re.findall(r"<(?:\w+:)?CadastralParcel\b.*?</(?:\w+:)?CadastralParcel>", xml, re.S):
        ref = re.search(r"nationalCadastralReference>([^<]+)<", feat)
        area = re.search(r"areaValue[^>]*>(\d+)<", feat)
        if ref and area:
            out[ref.group(1).split("-", 1)[1]] = int(area.group(1))
    return out


def _is_numeric_parcel(p: str) -> bool:
    # "st. 184" (building plot) is a different parcel than "184"; the WFS reference format for
    # building plots is unverified, so those are left for manual checking instead of risking a wrong match
    return bool(re.fullmatch(r"\d+(?:/\d+)?", p.strip()))


async def parcel_areas(ku_code: int, parcels: list[str], client: httpx.AsyncClient) -> dict[str, int | None]:
    numeric = [p for p in parcels if _is_numeric_parcel(p)]
    found: dict[str, int] = {}
    if numeric:
        resp = await client.get(WFS_URL, params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": "CP:CadastralParcel", "FILTER": wfs_filter(ku_code, numeric),
        })
        resp.raise_for_status()
        found = parse_wfs_areas(resp.text)
    return {p: found.get(p.strip()) for p in parcels}


def _has(items: list[str], word: str) -> bool:
    return any(word in i.lower() for i in items)


def assess_restrictions(
    restrictions: dict[str, list[str]],
    other_entries: list[str],
    price_records: dict[str, int] | None = None,
) -> list[dict]:
    """Turn LV restriction types into risk items {level, title, explain}. Levels: high | medium | low."""
    price_records = price_records or {}
    items: list[dict] = []
    all_r = [r for rs in restrictions.values() for r in rs]
    parcels_with = lambda word: sorted(p for p, rs in restrictions.items() if _has(rs, word))  # noqa: E731

    if _has(all_r, "zákaz zcizení"):
        ps = parcels_with("zákaz zcizení")
        explain = ("Vlastník nesmí nemovitost převést bez souhlasu oprávněné osoby. Bez výmazu zápisu "
                   "nelze koupit. Zjistěte v úplném výpisu z LV (část C), pro koho je zapsán a z jaké listiny.")
        if _has(all_r, "věcné břemeno"):
            explain += (" Kombinace se věcným břemenem typicky znamená darování v rodině s doživotním "
                        "právem bydlení dárce – břemeno by bez výmazu přešlo na kupce.")
        if ps and all(price_records.get(p, 0) == 0 for p in ps):
            explain += " Parcely nemají cenový údaj → vlastník je pravděpodobně nabyl darem nebo dědictvím."
        items.append({"level": "high", "title": f"Zákaz zcizení (parcely {', '.join(ps)})", "explain": explain})
    elif _has(all_r, "věcné břemeno"):
        ps = parcels_with("věcné břemeno")
        items.append({"level": "medium", "title": f"Věcné břemeno (parcely {', '.join(ps)})",
                      "explain": "Ověřte typ: cesta/inženýrské sítě bývají neškodné, právo bydlení/užívání přechází na kupce."})

    if _has(all_r, "zástavní právo"):
        ps = parcels_with("zástavní právo")
        items.append({"level": "low", "title": f"Zástavní právo (parcely {', '.join(ps)})",
                      "explain": "Typicky hypotéka. Řeší se standardně: vyčíslení zůstatku, úschova, doplacení bance, výmaz zástavy."})

    for entry in other_entries:
        low = entry.lower()
        if re.search(r"exekuc|insolvenc|plomba|nařízení výkonu|soudní spor", low):
            items.append({"level": "high", "title": entry,
                          "explain": "Probíhající řízení – převod může být neplatný nebo zablokovaný. Bez vyřešení nekupovat."})
        elif re.search(r"závazek.*zást", low):
            items.append({"level": "low", "title": entry, "explain": "Běžný doprovodný zápis k bankovní hypotéce."})
        else:
            items.append({"level": "medium", "title": entry, "explain": "Neznámý typ zápisu – ověřte v úplném výpisu z LV."})
    return items


def plot_check(listing_plot: int | None, built_area: int | None, total: int) -> str:
    if listing_plot is None:
        return f"inzerát výměru neuvádí; katastr {total:,} m²".replace(",", " ")
    if listing_plot == total:
        return "sedí s inzerátem"
    if built_area and listing_plot == total - built_area:
        return (f"sedí bez zastavěné plochy ({total} − {built_area} = {listing_plot} m²); "
                f"ve skutečnosti kupujete {total:,} m²").replace(",", " ")
    return f"nesedí: inzerát {listing_plot:,} m², katastr {total:,} m²".replace(",", " ")
