# tests/test_filters.py
from src.pipeline.filters import (
    TypeFilter, URLPatternFilter, PriceFilter, AreaFilter,
    LocationFilter, BlacklistFilter, FilterPipeline,
)
from src.models import NormalizedListing


def _make_listing(**overrides) -> NormalizedListing:
    defaults = dict(
        portal="sreality", portal_id="1", title="Test", url="https://example.com",
        type="pozemek", price=5000000, price_unknown=False,
        area_m2=1000, area_unknown=False, price_per_m2=5000,
        location="Baška", location_id="baska", coordinates=None,
    )
    defaults.update(overrides)
    return NormalizedListing(**defaults)


def test_type_filter_pass():
    f = TypeFilter(["dum", "pozemek"])
    assert f.check(_make_listing(type="pozemek")).passed is True


def test_type_filter_reject():
    f = TypeFilter(["dum", "pozemek"])
    assert f.check(_make_listing(type="byt")).passed is False


def test_price_filter_pass():
    f = PriceFilter(max_price=10000000)
    assert f.check(_make_listing(price=5000000)).passed is True


def test_price_filter_reject():
    f = PriceFilter(max_price=10000000)
    assert f.check(_make_listing(price=15000000)).passed is False


def test_price_filter_unknown_passes():
    f = PriceFilter(max_price=10000000)
    assert f.check(_make_listing(price=None, price_unknown=True)).passed is True


def test_area_filter_pass():
    f = AreaFilter(min_area=750)
    assert f.check(_make_listing(area_m2=1000)).passed is True


def test_area_filter_reject():
    f = AreaFilter(min_area=750)
    assert f.check(_make_listing(area_m2=500)).passed is False


def test_area_filter_unknown_passes():
    f = AreaFilter(min_area=750)
    assert f.check(_make_listing(area_m2=None, area_unknown=True)).passed is True


def test_location_filter_pass():
    f = LocationFilter({"baska", "frydek_mistek"})
    assert f.check(_make_listing(location_id="baska")).passed is True


def test_location_filter_reject():
    f = LocationFilter({"baska", "frydek_mistek"})
    assert f.check(_make_listing(location_id="trinec")).passed is False


def test_blacklist_filter_pass():
    f = BlacklistFilter(["pronájem", "les", "trinec"])
    assert f.check(_make_listing(title="Stavební pozemek Baška")).passed is True


def test_blacklist_filter_reject():
    f = BlacklistFilter(["pronájem", "les", "trinec"])
    assert f.check(_make_listing(title="Pronájem domu Baška")).passed is False


def test_blacklist_filter_diacritics_insensitive():
    f = BlacklistFilter(["třinec"])
    assert f.check(_make_listing(title="Pozemek Trinec")).passed is False


def test_url_pattern_filter_pass():
    f = URLPatternFilter(["zemedelsk", "komercni"])
    assert f.check(_make_listing(url="https://sreality.cz/prodej/pozemky/")).passed is True


def test_url_pattern_filter_reject():
    f = URLPatternFilter(["zemedelsk", "komercni"])
    assert f.check(_make_listing(url="https://sreality.cz/prodej/komercni-pozemky/")).passed is False


def test_pipeline_applies_all():
    pipeline = FilterPipeline.create(
        allowed_types=["pozemek"],
        max_price=10000000,
        min_area=750,
        active_locality_ids={"baska"},
        blacklist_words=["les"],
        url_blocked_patterns=["komercni"],
    )
    # Good listing passes
    assert pipeline.apply(_make_listing()) is True
    # Wrong type fails
    assert pipeline.apply(_make_listing(type="byt")) is False
    # Over price fails
    assert pipeline.apply(_make_listing(price=15000000)) is False
