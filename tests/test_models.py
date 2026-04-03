# tests/test_models.py
from src.models import RawListing, NormalizedListing


def test_raw_listing_creation():
    raw = RawListing(
        portal="sreality",
        portal_id="12345",
        title="Stavební pozemek 2,473 m²",
        url="https://sreality.cz/detail/12345",
        type_raw="Pozemky",
        price_raw="7 980 000 Kč",
        area_raw="2 473 m²",
        location_raw="Frýdlant nad Ostravicí",
    )
    assert raw.portal == "sreality"
    assert raw.images == []
    assert raw.coordinates is None


def test_normalized_listing_price_per_m2():
    listing = NormalizedListing(
        portal="sreality",
        portal_id="12345",
        title="Stavební pozemek",
        url="https://sreality.cz/detail/12345",
        type="pozemek",
        price=7980000,
        price_unknown=False,
        area_m2=2473,
        area_unknown=False,
        price_per_m2=3227,
        location="Frýdlant nad Ostravicí",
        location_id="frydlant",
        coordinates=(49.527, 18.359),
    )
    assert listing.price_per_m2 == 3227


def test_normalized_listing_to_dict():
    listing = NormalizedListing(
        portal="sreality",
        portal_id="12345",
        title="Test",
        url="https://example.com",
        type="dum",
        price=5000000,
        price_unknown=False,
        area_m2=1000,
        area_unknown=False,
        price_per_m2=5000,
        location="Baška",
        location_id="baska",
        coordinates=(49.64, 18.35),
    )
    d = listing.to_dict()
    assert d["id"] == "sreality_12345"
    assert d["status"] == "active"
    assert d["price_history"] == [{"date": d["added"], "price": 5000000}]
