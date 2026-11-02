"""Render a favourite's dossier as Markdown."""

from __future__ import annotations

from datetime import date

from src.dossier.favorites import KATASTR_TEMPLATE
from src.dossier.katastr import assess_restrictions, plot_check
from src.similar.details import ListingDetails

LEVEL_ICON = {"high": "⚠️ vysoké", "medium": "🔶 střední", "low": "✅ nízké"}
LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}


def _n(x) -> str:
    return f"{x:,}".replace(",", " ") if isinstance(x, int) else "?"


def _kc(x) -> str:
    return f"{_n(x)} Kč" if isinstance(x, int) else "neuvedena"


def _failed(value) -> str | None:
    return f"_nepodařilo se ověřit ({type(value).__name__}: {value})_" if isinstance(value, Exception) else None


def _val(v) -> str:
    if v is None:
        return "?"
    if v is True:
        return "ano"
    if v is False:
        return "ne"
    return str(v)


def _same_place(text: str | None, kat: dict) -> bool:
    from src.pipeline.normalizer import strip_diacritics
    hay = strip_diacritics(text or "").lower()
    return any(strip_diacritics(n).lower() in hay for n in (kat.get("obec"), kat.get("ku_name")) if n)


def _risk_items(kat: dict | None) -> list[dict]:
    if not kat:
        return []
    items = assess_restrictions(kat.get("restrictions") or {}, kat.get("other_entries") or [],
                                kat.get("price_records") or {})
    return sorted(items, key=lambda i: LEVEL_ORDER[i["level"]])


def build_report(fav: dict, details: ListingDetails | None, ctx: dict) -> str:
    d = details or ListingDetails(url=fav["url"], fetched=date.today().isoformat(), ok=False)
    listing = ctx.get("listing") or {}
    kat = fav.get("katastr")
    risks = _risk_items(kat)
    history = ctx.get("history")
    title = d.title or listing.get("title") or fav["url"]
    L: list[str] = []
    w = L.append

    w(f"# Dossier – {title}")
    w("")
    w(f"*Vygenerováno {date.today().isoformat()} z `python -m src.dossier build`. "
      "Soukromý dokument – obsahuje údaje z katastru a rejstříků, nepublikovat.*")
    if fav.get("note"):
        w(f"\n> Poznámka: {fav['note']}")
    w("")

    # --- summary ---
    if risks:
        risk = LEVEL_ICON[risks[0]["level"]]
    elif kat:
        risk = "✅ nízké – bez zapsaných omezení"
    else:
        risk = "❓ neznámé – doplňte údaje z katastru"
    first_seen = min((h.get("added") for h in history if h.get("added")), default=None) if isinstance(history, list) else None
    prices = sorted({h.get("price") for h in history if h.get("price")}) if isinstance(history, list) else []
    w("## Shrnutí")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Cena | **{_kc(listing.get('price'))}**" + (f" (dříve {_kc(d.old_price)})" if d.old_price else "") + " |")
    w(f"| Lokalita | {listing.get('location') or '?'} |")
    w(f"| Užitná plocha / pozemek | {_n(d.usable_area)} m² / {_n(d.plot_area or listing.get('area_m2'))} m² |")
    w(f"| Dispozice, rok | {_val(d.disposition)}, {_val(d.year_built)} |")
    w(f"| Stav, PENB | {_val(d.condition)}, {_val(d.penb)} |")
    w(f"| Vytápění | {_val(d.heating)} |")
    w(f"| Odpad, plyn | {_val(d.sewer)}, {_val(d.gas)} |")
    w(f"| Právní riziko | **{risk}** |")
    w(f"| V prodeji nejméně od | {first_seen or d.listed_since or '?'} |")
    if len(prices) > 1:
        w(f"| Ceny v historii | {', '.join(_kc(p) for p in prices)} |")
    w("")

    # --- listing ---
    w("## Inzerát")
    w("")
    w(f"- URL: {fav['url']}")
    if not d.ok:
        w("- Detail inzerátu: _nepodařilo se ověřit (stránka nedostupná nebo stažená)_")
    for label, value in [
        ("Užitná plocha", f"{_n(d.usable_area)} m²" if d.usable_area else None),
        ("Pozemek", f"{_n(d.plot_area)} m²" if d.plot_area else None),
        ("Zastavěná plocha", f"{_n(d.built_area)} m²" if d.built_area else None),
        ("Dispozice", d.disposition), ("Rok kolaudace/výstavby", d.year_built), ("Stav", d.condition),
        ("Konstrukce", d.construction), ("Vytápění", d.heating), ("Odpad", d.sewer), ("Plyn", d.gas),
        ("PENB", d.penb), ("RK", d.agency), ("Makléř", d.agent), ("Číslo zakázky", d.ref_number),
        ("Vloženo", d.listed_since),
    ]:
        if value is not None:
            w(f"- {label}: {_val(value)}")
    if d.description:
        w("")
        w("> " + d.description[:800] + ("…" if len(d.description) > 800 else ""))
    w("")

    # --- history ---
    w("## Historie inzerce")
    w("")
    if (err := _failed(history)):
        w(err)
    elif not history:
        w("_V datech monitoringu nenalezeno (monitoring běží od 4/2026)._")
    else:
        w("| Portál | Odkaz | Na webu | Cena |")
        w("|---|---|---|---|")
        for h in history:
            span = f"{h.get('added')} – {h.get('removed_date') or '**aktivní**'}"
            w(f"| {h.get('portal')} | [{h.get('id')}]({h.get('url')}) | {span} | {_kc(h.get('price'))} |")
    w("")

    # --- cadastre ---
    w("## Katastr")
    w("")
    if not kat:
        w("Údaje z katastru zatím chybí. Nahlížení do KN neumožňuje automatické dotazy, doplňte je ručně:")
        w("")
        w("1. Na https://nahlizenidokn.cuzk.cz → *Vyhledat parcelu / budovu* najděte dům (obec, č. p. nebo mapa).")
        w("2. Otevřete *Seznam nemovitostí na LV* a opište čísla parcel, vlastníky, omezení vlastnického práva a jiné zápisy.")
        w("3. Vložte do `private/favorites.json` ke klíči `katastr` tohoto inzerátu a spusťte `python -m src.dossier build` znovu:")
        w("")
        w("```json")
        w(KATASTR_TEMPLATE)
        w("```")
    else:
        areas = ctx.get("parcel_areas")
        w(f"- Katastrální území: {kat.get('ku_name') or '?'} [{kat.get('ku_code')}], LV **{kat.get('lv')}**")
        w(f"- Vlastník: {', '.join(kat.get('owners') or []) or '?'}")
        w("")
        if (err := _failed(areas)):
            w(f"Výměry parcel (ČÚZK WFS): {err}")
            areas = {}
        w("| Parcela | Výměra | Omezení | Cenové údaje |")
        w("|---|---|---|---|")
        total = 0
        for p in kat.get("parcels") or []:
            a = (areas or {}).get(p)
            total += a or 0
            restr = "; ".join((kat.get("restrictions") or {}).get(p, [])) or "žádná"
            w(f"| {p} | {_n(a)} m² | {restr} | {(kat.get('price_records') or {}).get(p, '?')} |")
        if total:
            w(f"| **Celkem** | **{_n(total)} m²** | {plot_check(d.plot_area, d.built_area, total)} | |")
        w("")
        if kat.get("other_entries"):
            w("Jiné zápisy: " + "; ".join(kat["other_entries"]))
            w("")
        if risks:
            w("### Posouzení omezení")
            w("")
            for r in risks:
                w(f"- {LEVEL_ICON[r['level']]} – **{r['title']}**: {r['explain']}")
        else:
            w("Na LV nejsou zapsána žádná omezení ani jiné zápisy. ✅")
    w("")

    # --- owners ---
    owners = (kat or {}).get("owners") or []
    if owners:
        w("## Vlastník – veřejné rejstříky")
        w("")
        ares, isir = ctx.get("ares"), ctx.get("isir")
        for o in owners:
            w(f"### {o}")
            if (err := _failed(ares)):
                w(f"- ARES: {err}")
            else:
                hits = (ares or {}).get(o, [])
                if not hits:
                    w("- ARES: bez záznamu podnikatele")
                for h in hits:
                    state = f"zaniklo {h['until']}" if h.get("until") else "aktivní"
                    who = ("✓ sídlo v obci – pravděpodobně stejná osoba" if _same_place(h.get("address"), kat)
                           else "⚠️ sídlo jinde – pravděpodobně jmenovec")
                    w(f"- ARES: {h['name']}, IČO {h['ico']}, sídlo {h.get('address')}, od {h.get('since')} ({state}) – {who}")
            if (err := _failed(isir)):
                w(f"- ISIR: {err}")
            else:
                hits = (isir or {}).get(o, [])
                if not hits:
                    w("- ISIR: žádný dlužník tohoto jména ✅")
                for h in hits:
                    who = ("**bydliště v obci – pravděpodobně stejná osoba, ověřte!**" if _same_place(h.get("city"), kat)
                           else "bydliště jinde – pravděpodobně jmenovec")
                    w(f"- ISIR: {h['name']} (nar. {h.get('birth_year') or '?'}, {h.get('city') or '?'}), "
                      f"{h.get('case')}, {h.get('state')} – {who}")
            w("")

    # --- municipality ---
    w("## Kanalizace a obec")
    w("")
    w(f"- Odpad podle inzerátu: {_val(d.sewer)}")
    tenders = ctx.get("tenders")
    if (err := _failed(tenders)):
        w(f"- Veřejné zakázky (TED): {err}")
    elif not tenders:
        w("- Veřejné zakázky na kanalizaci/ČOV v obci (TED): nenalezeny")
    else:
        w("- Veřejné zakázky na kanalizaci/ČOV (TED):")
        for t in tenders:
            w(f"  - {t['date']} – [{t['id']}]({t['url']}) – {t['type']} – {t.get('title')}")
        if any("smlouva uzavřena" in t["type"] for t in tenders):
            w("  - ➡️ Zakázka je zadaná; termíny a rozsah (domovní čerpací šachty, etapy) ověřte na obci.")
    w("")

    # --- market ---
    w("## Trh")
    w("")
    market = ctx.get("market")
    if (err := _failed(market)):
        w(err)
    else:
        for label, key in [("Obec", "locality"), ("Celá sledovaná oblast", "area")]:
            s = (market or {}).get(key) or {"count": 0}
            if s.get("count"):
                w(f"- {label}: {s['count']} aktivních domů, medián {_kc(s['median'])} (min {_kc(s['min'])}, max {_kc(s['max'])})")
            else:
                w(f"- {label}: žádná data")
        if isinstance(listing.get("price"), int) and d.usable_area:
            w(f"- Cena za m² užitné plochy: {_n(round(listing['price'] / d.usable_area))} Kč/m²")
    w("")

    # --- checklist ---
    w("## Co ještě udělat")
    w("")
    if not kat:
        w("- [ ] Doplnit údaje z katastru (viz výše)")
    else:
        w(f"- [ ] Úplný výpis z LV {kat.get('lv')} (Czech POINT nebo od RK) – část C: pro koho jsou omezení a z jaké listiny")
    for r in risks:
        if r["level"] == "high":
            w(f"- [ ] Vyřešit: {r['title']} – písemně od RK, jak a kdy bude vymazáno")
        elif r["level"] == "low" and "zástav" in r["title"].lower():
            w("- [ ] Vyčíslení zůstatku úvěru a souhlas banky s výmazem zástavy; platba přes úschovu")
    if d.sewer and ("septik" in d.sewer or "jímk" in d.sewer):
        w("- [ ] Na obci: termín kanalizace v ulici, kdo platí přípojku a čerpací šachtu, poplatky")
    if d.penb in ("F", "G"):
        w("- [ ] Odhad nákladů na zateplení a topení (PENB " + d.penb + ")")
    w("- [ ] Prohlídka: střecha, krov, vlhkost sklepa, elektroinstalace, revize kotle a komínů")
    w("- [ ] Povodňové mapy (https://www.povis.cz) a územní plán obce")
    w("")
    w("## Zdroje")
    w("")
    w(f"- Inzerát: {fav['url']}")
    w("- Katastr: https://nahlizenidokn.cuzk.cz (ručně), výměry: ČÚZK INSPIRE WFS")
    w("- ARES: https://ares.gov.cz · ISIR: https://isir.justice.cz · TED: https://ted.europa.eu")
    w("- Historie a trh: data projektu reality-fetcher-v2")
    return "\n".join(L) + "\n"
