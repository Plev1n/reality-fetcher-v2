# All people, addresses and IDs in this file are fictional.
from src.dossier.katastr import assess_restrictions, parse_wfs_areas, plot_check, wfs_filter
from src.dossier.registries import parse_ares, parse_isir
from src.dossier.history import match_history
from src.dossier.market import market_stats
from src.dossier.municipality import parse_ted
from src.dossier.report import build_report
from src.similar.details import ListingDetails

WFS_XML = """<FeatureCollection><member><cp:CadastralParcel gml:id="x">
<cp:areaValue uom="m2">166</cp:areaValue><cp:label>12</cp:label>
<cp:nationalCadastralReference>600001-12</cp:nationalCadastralReference>
</cp:CadastralParcel></member><member><cp:CadastralParcel gml:id="y">
<cp:areaValue uom="m2">537</cp:areaValue><cp:label>13/1</cp:label>
<cp:nationalCadastralReference>600001-13/1</cp:nationalCadastralReference>
</cp:CadastralParcel></member></FeatureCollection>"""


def test_parse_wfs_areas():
    assert parse_wfs_areas(WFS_XML) == {"12": 166, "13/1": 537}


def test_wfs_filter_or_for_many():
    f = wfs_filter(600001, ["10", "11"])
    assert "<fes:Or>" in f and "600001-10" in f and "600001-11" in f
    assert "<fes:Or>" not in wfs_filter(600001, ["10"])


def test_assess_gift_with_usufruct_high():
    res = assess_restrictions(
        {"10": ["Věcné břemeno (podle listiny)", "Zákaz zcizení"],
         "11": ["Věcné břemeno (podle listiny)", "Zákaz zcizení"]},
        [], {"10": 0, "11": 0, "12": 1})
    highs = [r for r in res if r["level"] == "high"]
    assert highs and any("zákaz zcizení" in r["title"].lower() for r in highs)
    assert any("dar" in r["explain"] for r in res)


def test_assess_mortgage_low():
    res = assess_restrictions(
        {"10": ["Zástavní právo smluvní"]},
        ["Závazek neumožnit zápis nového zást. práva namísto starého"], {})
    assert res and {r["level"] for r in res} == {"low"}


def test_assess_execution_high():
    res = assess_restrictions({}, ["Zahájení exekuce"], {})
    assert res[0]["level"] == "high"


def test_assess_easement_alone_medium():
    res = assess_restrictions({"1": ["Věcné břemeno chůze a jízdy"]}, [], {})
    assert [r["level"] for r in res] == ["medium"]


def test_plot_check():
    assert plot_check(1375, 100, 1375).startswith("sedí")
    assert "bez zastavěné plochy" in plot_check(1198, 93, 1291)
    assert plot_check(2000, 93, 1291).startswith("nesedí")
    assert plot_check(None, None, 1291).startswith("inzerát")


def test_parse_ares():
    data = {"pocetCelkem": 1, "ekonomickeSubjekty": [{"ico": "12345678", "obchodniJmeno": "Jan Novák",
            "sidlo": {"textovaAdresa": "č.p. 1, 70000 Testov"}, "datumVzniku": "1995-01-01"}]}
    assert parse_ares(data) == [{"ico": "12345678", "name": "Jan Novák", "address": "č.p. 1, 70000 Testov",
                                 "since": "1995-01-01", "until": None}]


ISIR_HTML = """<html><body>POČET NALEZENÝCH DLUŽNÍKŮ 1
<table class="vysledekLustrace"><tr><th><I>Spisová značka:</i></th><td><b><span> KSOS 1 INS 1 / 2020 </span></b>
<i>Vedená u <B><span>Krajského soudu v Ostravě</span></B></I></TD></TR></table>
<table class="vysledekLustrace"><TR><Th><I> Jméno/název: </I></Th><TD><B><span> Jan Novák </span></B></TD></TR>
<TR><Th><I>IČ:</I></Th><TD><B><span> </span></B></TD></TR>
<TR><Th><I>Rodné číslo / Datum nar.:</I></Th><TD><B><span> 900101/1234 / 01.01.1990 </span></B></TD></TR>
<TR><Th><I> Bydliště: </I></Th><Td><B><span> Testov, Smyšlená 1/1, PSČ 700 00</span></B></TD></TR></TABLE>
<table><TR><Th><I>Stav řízení:</I></Th><TD><B><span> Odškrtnutá - skončená věc </span></B></TD></TR></table>
</body></html>"""


def test_isir_no_birth_number_or_street():
    res = parse_isir(ISIR_HTML)
    assert res == [{"name": "Jan Novák", "case": "KSOS 1 INS 1 / 2020", "birth_year": "1990",
                    "city": "Testov", "state": "Odškrtnutá - skončená věc"}]
    assert "900101" not in str(res) and "Smyšlená" not in str(res)


def test_isir_zero():
    assert parse_isir("<html><body>POČET NALEZENÝCH DLUŽNÍKŮ 0</body></html>") == []


def test_parse_ted():
    data = {"notices": [{"publication-number": "1-2026", "publication-date": "2026-10-21+02:00",
                         "notice-title": {"ces": "Česko – Testov - splašková kanalizace a ČOV"},
                         "notice-type": "can-standard", "buyer-name": {"ces": ["Obec Testov"]}}]}
    assert parse_ted(data) == [{"id": "1-2026", "date": "2026-10-21", "title": "Česko – Testov - splašková kanalizace a ČOV",
                                "type": "oznámení o zadání zakázky (smlouva uzavřena)", "buyer": "Obec Testov",
                                "url": "https://ted.europa.eu/cs/notice/-/detail/1-2026"}]


def _hl(id_, title, price, loc, added="2026-06-15", removed=None, portal="bazos", area=None):
    return {"id": id_, "title": title, "price": price, "location_id": loc, "added": added,
            "removed_date": removed, "status": "removed" if removed else "active", "portal": portal,
            "url": f"https://x/{id_}", "type": "dum", "area_m2": area, "price_history": []}


def test_match_history_by_price_and_name():
    target = _hl("idnes_t", "prodej domu 135 m² s pozemkem 1 375 m²", 5500000, "przno", portal="idnes")
    pool = [
        _hl("bazos_1", "Prodej rodinného domu, Pržno", 5500000, "frydek_mistek", removed="2026-07-13"),
        _hl("bazos_2", "Prodej hrubé stavby, Palkovice", 5500000, "palkovice"),
        _hl("realingo_3", "Rodinny dum, Pržno", None, "przno", area=989),
        _hl("idnes_t", "prodej domu 135 m² s pozemkem 1 375 m²", 5500000, "przno", portal="idnes"),
    ]
    ids = [h["id"] for h in match_history(target, "Pržno", 1375, pool)]
    assert ids == ["bazos_1", "idnes_t"]


def test_market_stats():
    data = {"listings": [
        {"type": "dum", "status": "active", "price": p, "location_id": loc}
        for p, loc in [(5_000_000, "przno"), (7_000_000, "przno"), (6_000_000, "baska"), (100_000, "przno")]
    ]}
    s = market_stats(data, "przno")
    assert s["locality"] == {"count": 2, "median": 6_000_000, "min": 5_000_000, "max": 7_000_000}
    assert s["area"]["count"] == 3


def _fav(katastr=None):
    return {"url": "https://reality.idnes.cz/detail/prodej/dum/testov/abc/", "added": "2026-11-02",
            "note": None, "katastr": katastr}


def _det():
    return ListingDetails(url="u", fetched="2026-11-02", title="Prodej domu 135 m² s pozemkem 1 375 m²",
                          usable_area=135, plot_area=1375, built_area=100, rooms=5, disposition="5+kk",
                          year_built=1960, sewer="septik / jímka", penb="G")


def test_report_with_failed_sources():
    err = RuntimeError("timeout")
    ctx = {"listing": {"price": 5500000, "location": "Testov", "location_id": "testov", "portal": "idnes"},
           "history": err, "market": err, "tenders": err, "parcel_areas": err, "ares": err, "isir": err}
    md = build_report(_fav({"ku_code": 600001, "ku_name": "Testov", "lv": 1, "parcels": ["10"],
                            "owners": ["Novák Jan"], "restrictions": {}}), _det(), ctx)
    assert "## Inzerát" in md
    assert md.count("nepodařilo se ověřit") >= 4
    assert "135 m²" in md


def test_report_without_katastr_has_guide():
    ctx = {"listing": {"price": 5500000, "location": "Testov", "location_id": "testov"},
           "history": [], "market": {"locality": {"count": 0}, "area": {"count": 0}}, "tenders": []}
    md = build_report(_fav(), _det(), ctx)
    assert "nahlizenidokn.cuzk.cz" in md
    assert '"ku_code"' in md
    assert "## Vlastník" not in md


def test_report_full():
    kat = {"ku_code": 600001, "ku_name": "Testov", "lv": 1, "parcels": ["10", "11", "12"],
           "owners": ["Novák Jan"],
           "restrictions": {"10": ["Věcné břemeno (podle listiny)", "Zákaz zcizení"]},
           "other_entries": [], "price_records": {"10": 0, "12": 1}}
    ctx = {"listing": {"price": 5500000, "location": "Testov", "location_id": "testov", "portal": "idnes"},
           "history": [_hl("bazos_1", "Prodej rodinného domu, Testov", 5500000, "testov", removed="2026-07-13")],
           "market": {"locality": {"count": 2, "median": 6_000_000, "min": 5_000_000, "max": 7_000_000},
                      "area": {"count": 100, "median": 5_900_000, "min": 1, "max": 9}},
           "tenders": [{"id": "1-2026", "date": "2026-10-21", "title": "Testov - splašková kanalizace a ČOV",
                        "type": "oznámení o zadání zakázky (smlouva uzavřena)", "buyer": "Obec Testov", "url": "https://t"}],
           "parcel_areas": {"10": 503, "11": 736, "12": 136},
           "ares": {"Novák Jan": [{"ico": "12345678", "name": "Jan Novák", "address": "č.p. 1, 70000 Testov",
                                    "since": "1995-01-01", "until": None}]},
           "isir": {"Novák Jan": []}}
    md = build_report(_fav(kat), _det(), ctx)
    assert "1 375 m²" in md and "sedí" in md
    assert "⚠️" in md and "Zákaz zcizení" in md
    assert "12345678" in md
    assert "žádný dlužník" in md
    assert "1-2026" in md
    assert "- [ ]" in md  # checklist


def test_parse_ted_drops_unrelated():
    data = {"notices": [{"publication-number": "2-2026", "publication-date": "2026-08-12+02:00",
                         "notice-title": {"ces": "Česko – Speciální pracovní oděvy – Zásahové obleky"},
                         "notice-type": "can-standard"}]}
    assert parse_ted(data) == []


def test_report_flags_namesakes_by_address():
    kat = {"obec": "Testov", "ku_code": 600001, "ku_name": "Testov", "lv": 1, "parcels": [],
           "owners": ["Novák Jan"], "restrictions": {}}
    ctx = {"listing": {"price": 1, "location": "Testov"}, "history": [], "market": {}, "tenders": [],
           "parcel_areas": {},
           "ares": {"Novák Jan": [
               {"ico": "1", "name": "Jan Novák", "address": "č.p. 1, 70000 Testov", "since": "2000-01-01", "until": None},
               {"ico": "2", "name": "Jan Novák", "address": "Praha 4", "since": "2001-01-01", "until": None}]},
           "isir": {"Novák Jan": [{"name": "Jan Novák", "case": "X", "birth_year": "1990", "city": "Praha", "state": "s"}]}}
    md = build_report(_fav(kat), _det(), ctx)
    lines = [l for l in md.splitlines() if l.startswith("- ARES") or l.startswith("- ISIR")]
    assert "sídlo v obci" in lines[0]
    assert "jmenovec" in lines[1]
    assert "jmenovec" in lines[2]


def test_isir_ignores_search_criteria_table():
    html = ISIR_HTML.replace("<body>", "<body><table><tr><th>Příjmení/název:</th><td><span>Novák</span></td></tr></table>")
    assert [r["name"] for r in parse_isir(html)] == ["Jan Novák"]


def test_building_plot_not_looked_up():
    import asyncio
    from src.dossier.katastr import parcel_areas

    class Resp:
        text = WFS_XML
        def raise_for_status(self): pass

    class Client:
        params = None
        async def get(self, url, params):
            Client.params = params
            return Resp()

    res = asyncio.run(parcel_areas(600001, ["12", "st. 12"], Client()))
    assert res == {"12": 166, "st. 12": None}
    assert "st. 12" not in Client.params["FILTER"]
