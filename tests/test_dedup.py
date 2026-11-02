# tests/test_dedup.py
from src.pipeline.dedup import deduplicate, _normalize_title, _numeric_fingerprint, _price_area_key
from src.models import NormalizedListing


def _make(portal="sreality", portal_id="1", title="Test", price=5000000, area=1000, **kw):
    defaults = dict(
        url="https://example.com", type="pozemek", price_unknown=False,
        area_unknown=False, price_per_m2=5000, location="Baška",
        location_id="baska", coordinates=None,
    )
    defaults.update(kw)
    return NormalizedListing(portal=portal, portal_id=portal_id, title=title,
                             price=price, area_m2=area, **defaults)


def test_normalize_title():
    assert _normalize_title("Prodej rodinného domu 180 m²") == _normalize_title("Prodej rodinneho domu 180 m2")


def test_numeric_fingerprint():
    fp = _numeric_fingerprint("Stavební pozemek 2473 m², cena 7980000")
    assert "2473" in fp
    assert "7980000" in fp


def test_price_area_key():
    assert _price_area_key(7980000, 2473) == "pa_7980000_2473"
    assert _price_area_key(None, 2473) == ""
    assert _price_area_key(50, 2473) == ""  # price too low


def test_dedup_exact_title():
    a = _make(portal="sreality", portal_id="1", title="Stavební pozemek 2473 m²")
    b = _make(portal="bazos", portal_id="2", title="Stavební pozemek 2473 m²")
    result = deduplicate([a, b])
    assert len(result) == 1
    assert result[0].portal == "sreality"  # Higher priority


def test_dedup_price_area_match():
    a = _make(portal="sreality", portal_id="1", title="Nice house", price=7980000, area=2473)
    b = _make(portal="bazos", portal_id="2", title="Different title", price=7980000, area=2473)
    result = deduplicate([a, b])
    assert len(result) == 1
    assert result[0].portal == "sreality"


def test_dedup_no_match():
    a = _make(portal="sreality", portal_id="1", title="House A", price=5000000, area=1000)
    b = _make(portal="bazos", portal_id="2", title="House B", price=3000000, area=500)
    result = deduplicate([a, b])
    assert len(result) == 2


def test_dedup_keeps_higher_priority():
    a = _make(portal="bazos", portal_id="1", title="Same listing")
    b = _make(portal="idnes", portal_id="2", title="Same listing")
    c = _make(portal="sreality", portal_id="3", title="Same listing")
    result = deduplicate([a, b, c])
    assert len(result) == 1
    assert result[0].portal == "sreality"


def test_same_price_different_village_not_merged():
    a = _make(portal="idnes", portal_id="1", title="prodej domu 110 m² s pozemkem 1 198 m²",
              price=5990000, area=1198, type="dum", location="Kunčičky u Bašky", location_id="kuncicky_u_basky")
    b = _make(portal="sreality", portal_id="2", title="Prodej rodinného domu 200 m², pozemek 10918 m²",
              price=5990000, area=10918, type="dum", location="Ostravice", location_id="ostravice")
    assert len(deduplicate([a, b])) == 2


def test_generic_title_different_price_not_merged():
    a = _make(portal="bazos", portal_id="1", title="Prodej rodinného domu", price=4500000, area=None)
    b = _make(portal="bazos", portal_id="2", title="Prodej rodinného domu", price=7200000, area=None)
    assert len(deduplicate([a, b])) == 2


def test_same_area_different_village_not_merged():
    a = _make(portal="bazos", portal_id="1", title="A", price=3000000, area=1375, location_id="przno")
    b = _make(portal="realingo", portal_id="2", title="B", price=4000000, area=1375, location_id="baska")
    assert len(deduplicate([a, b])) == 2


def test_house_and_plot_same_price_not_merged():
    a = _make(portal="sreality", portal_id="1", title="Dům", price=2490000, area=1065, type="dum")
    b = _make(portal="sreality", portal_id="2", title="Pozemek", price=2490000, area=1065, type="pozemek")
    assert len(deduplicate([a, b])) == 2


def test_same_house_generic_location_on_bazos_still_merged_by_price_area():
    a = _make(portal="idnes", portal_id="1", title="prodej domu 135 m² s pozemkem 1 375 m²",
              price=5500000, area=1375, type="dum", location_id="przno")
    b = _make(portal="bazos", portal_id="2", title="Prodej rodinného domu, Pržno",
              price=5500000, area=1375, type="dum", location_id="frydek_mistek")
    assert len(deduplicate([a, b])) == 1
