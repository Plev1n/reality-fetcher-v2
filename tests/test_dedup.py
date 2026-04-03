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
