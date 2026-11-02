from src.similar.details import (
    ListingDetails, parse_details, parse_sreality_detail,
    details_to_dict, details_from_dict,
)

IDNES_HTML = """<html><body>
<h1 class="b-detail__title"><span>Prodej domu 135 m² s pozemkem 1 375 m²</span></h1>
<div class="b-desc"><p>BO. vám nabízí k prodeji rodinný dům o dispozici 5+kk.
Vytápění: na tuhá paliva<br>Voda: obecní vodovod</p></div>
<div class="b-definition-columns"><dl>
<dt>Číslo zakázky</dt><dd>IDNES-8391</dd>
<dt>Cena</dt><dd>5&zwj;&nbsp;500&zwj;&nbsp;000&zwj;&nbsp;Kč</dd>
<dt>Konstrukce budovy</dt><dd><a href="#">cihlová</a></dd>
<dt>Stav budovy</dt><dd><a href="#"> před rekonstrukcí </a></dd>
<dt>Kolaudace</dt><dd>1960</dd>
<dt>Plocha pozemku</dt><dd>1375 m<sup>2</sup></dd>
<dt>Zastavěná plocha</dt><dd>100 m<sup>2</sup></dd>
<dt>Užitná plocha</dt><dd>135 m<sup>2</sup></dd>
<dt>Odpad</dt><dd>septik / jímka</dd>
<dt>PENB</dt><dd>G (vyhl. č. 264/2020 Sb.)</dd>
</dl></div>
<script>dataLayer.push({"listing_brand":"BO! reality a finance s.r.o.","listing_price":5500000});</script>
</body></html>"""

URL = "https://reality.idnes.cz/detail/prodej/dum/przno/6a0462f2ac3cc251a50f6853/"


def test_idnes_dl_parse():
    d = parse_details(IDNES_HTML, URL)
    assert d.ok
    assert d.usable_area == 135
    assert d.plot_area == 1375
    assert d.built_area == 100
    assert d.year_built == 1960
    assert d.sewer == "septik / jímka"
    assert d.penb == "G"
    assert d.ref_number == "IDNES-8391"
    assert d.rooms == 5
    assert d.disposition == "5+kk"
    assert d.condition == "před rekonstrukcí"
    assert d.construction == "cihlová"
    assert d.heating == "na tuhá paliva"
    assert d.agency == "BO! reality a finance s.r.o."
    assert d.price == 5500000


def test_bazos_text_parse():
    html = """<html><body><h1>Prodej rodinného domu, Pržno</h1><div class="popisdetail">
    BO! vám nabízí k prodeji rodinný dům o dispozici  5+kk. Dům je kompletně podsklepen.<br>
    zastavěná plocha (m2): 100<br>užitná plocha (m2): 135<br>plocha parcely (m2): 1375<br>
    </div></body></html>"""
    d = parse_details(html, "https://reality.bazos.cz/inzerat/223871005/x.php")
    assert (d.usable_area, d.plot_area, d.built_area, d.rooms) == (135, 1375, 100, 5)


def test_title_fallback_two_areas():
    d = parse_details("<html><body><h1>Prodej domu 110 m² s pozemkem 1 198 m²</h1></body></html>", URL)
    assert d.usable_area == 110
    assert d.plot_area == 1198


def test_title_fallback_comma_form():
    d = parse_details("<html><body><h1>Prodej rodinného domu 110 m², pozemek 1198 m²</h1></body></html>", URL)
    assert (d.usable_area, d.plot_area) == (110, 1198)


def test_gas_and_sewer_from_text():
    html = """<html><body><p>Dům je napojen na obecní vodovod, elektřinu. plyn a kanalizaci.
    Je vytápěn plynovým kotlem. Kolaudace v roce 1968. Dispozice 4+1.</p></body></html>"""
    d = parse_details(html, URL)
    assert d.gas is True
    assert d.sewer == "veřejná kanalizace"
    assert d.year_built == 1968
    assert d.rooms == 4


def test_planned_sewer_is_not_connected():
    html = """<html><body><p>Odpad: septik. V obci je plánovaná výstavba kanalizace.</p></body></html>"""
    assert parse_details(html, URL).sewer == "septik / jímka"


def test_empty_page_not_ok():
    d = parse_details("", URL)
    assert d.ok is False


def test_sreality_detail():
    result = {
        "advert_name": "Prodej rodinného domu 200 m², pozemek 10918 m²",
        "advert_code": "134916", "advert_description": "Popis",
        "building_area": 100, "usable_area": 200, "estate_area": 10918,
        "building_condition": {"name": "Před rekonstrukcí", "value": 8},
        "building_type": {"name": "Cihlová", "value": 2},
        "energy_efficiency_rating_cb": {"name": "G - Mimořádně nehospodárná", "value": 7},
        "gas_set": [], "gully_set": [{"name": "Jímka", "value": 4}],
        "heating_source_set": [{"name": "Krbová kamna", "value": 8}, {"name": "Kotel na tuhá paliva", "value": 10}],
        "room_count_cb": {"name": "5 a více pokojů", "value": 5},
        "acceptance_year": None, "since": "2026-03-12",
        "price_summary_czk": 5990000.0, "price_summary_old_czk": 6249000.0,
        "user": {"user_name": "Jana Nováková"},
    }
    d = parse_sreality_detail(result, "https://www.sreality.cz/detail/prodej/dum/rodinny/ostravice/1116820300")
    assert (d.usable_area, d.plot_area, d.built_area) == (200, 10918, 100)
    assert d.condition == "před rekonstrukcí"
    assert d.penb == "G"
    assert d.sewer == "jímka"
    assert d.gas is False
    assert d.heating == "krbová kamna, kotel na tuhá paliva"
    assert d.rooms == 5
    assert d.listed_since == "2026-03-12"
    assert d.old_price == 6249000
    assert d.ref_number == "134916"


def test_roundtrip_dict():
    d = parse_details(IDNES_HTML, URL)
    assert details_from_dict(details_to_dict(d)) == d


def test_description_container_ignores_other_listings():
    html = """<html><body><h1>Prodej rodinného domu, Pržno</h1>
    <div class="popisdetail">Kanalizace: v obci je na letošní rok (2026) plánovaná výstavba nové
    splaškové kanalizace s přímou možností budoucího připojení domu. Odpad řešen septikem.</div>
    <div class="inzeraty">Jiný dům postaven 2000, napojen na kanalizaci.</div></body></html>"""
    d = parse_details(html, "https://reality.bazos.cz/inzerat/1/x.php")
    assert d.year_built is None
    assert d.sewer == "septik / jímka"


def test_planned_sewer_label_first():
    html = """<html><body><div class="popisdetail">Kanalizace: v obci je na letošní rok (2026)
    plánovaná výstavba nové splaškové kanalizace.</div></body></html>"""
    assert parse_details(html, URL).sewer is None


def test_heating_from_passive_sentence():
    html = """<html><body><p>Je vytápěn plynovým kotlem a krbovými kamny.</p></body></html>"""
    assert parse_details(html, URL).heating == "plynovým kotlem a krbovými kamny"


def test_dot_thousands_separator():
    d = parse_details("<html><body><p>Plocha pozemku 1.250 m2, užitná plocha 140 m2.</p></body></html>", URL)
    assert d.plot_area == 1250 and d.usable_area == 140


def test_tiny_area_is_unknown():
    d = parse_details("<html><body><p>Plocha pozemku: 1 m2 (viz foto)</p></body></html>", URL)
    assert d.plot_area is None


def test_gas_negation():
    d = parse_details("<html><body><p>Plyn v obci není, vytápění elektrokotlem.</p></body></html>", URL)
    assert d.gas is not True


def test_penb_lowercase_word_ignored():
    d = parse_details("<html><body><p>PENB a revize doložíme.</p></body></html>", URL)
    assert d.penb is None


def test_title_m2_and_disposition_not_glued():
    d = parse_details("<html><body><h1>Prodej domu 5+1 140 m2, pozemek 1 016 m2</h1></body></html>", URL)
    assert (d.usable_area, d.plot_area) == (140, 1016)
