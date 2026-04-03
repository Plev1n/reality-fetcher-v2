"""Tests for normalization functions — especially the v1 area parsing bug fix."""

from src.pipeline.normalizer import (
    normalize_type,
    normalize_price,
    normalize_area,
    resolve_location,
    normalize_listing,
    strip_diacritics,
)
from src.models import RawListing


# --- Type normalization ---

def test_type_from_raw():
    assert normalize_type("Rodinné domy", "") == "dum"
    assert normalize_type("Pozemky", "") == "pozemek"
    assert normalize_type("Byty", "") == "byt"
    assert normalize_type("Rodinný dům", "") == "dum"
    assert normalize_type("Stavební pozemek", "") == "pozemek"
    assert normalize_type("Byt", "") == "byt"


def test_type_from_url_fallback():
    assert normalize_type("Unknown", "/prodej/domy/detail") == "dum"
    assert normalize_type("Unknown", "/prodej/pozemky/detail") == "pozemek"
    assert normalize_type("Unknown", "/prodej/byty/detail") == "byt"
    assert normalize_type("Unknown", "/nemovitosti/prodej/domy/") == "dum"


def test_type_remax_land_misclassification():
    """RE/MAX labels land as Dům — URL should override."""
    assert normalize_type("Dům", "/reality/pozemky/prodej/moravskoslezsky-kraj/detail") == "pozemek"


# --- Price normalization ---

def test_price_normal():
    assert normalize_price("7 980 000 Kč") == (7980000, False)
    assert normalize_price("3,840,000 CZK") == (3840000, False)
    assert normalize_price("2560000") == (2560000, False)


def test_price_unknown():
    assert normalize_price("Cena na vyžádání") == (None, True)
    assert normalize_price("Na vyžádání") == (None, True)
    assert normalize_price("Info o ceně u RK") == (None, True)
    assert normalize_price(None) == (None, True)
    assert normalize_price("dohodou") == (None, True)


def test_price_one_czk():
    """Symbolic 1 Kč prices should be treated as unknown."""
    assert normalize_price("1 Kč") == (None, True)


# --- Area normalization (THE BIG FIX) ---

def test_area_normal():
    assert normalize_area("2 473 m²") == (2473, False)
    assert normalize_area("800 m2") == (800, False)
    assert normalize_area("1 200m²") == (1200, False)


def test_area_room_count_not_concatenated():
    """v1 bug: '3+1 65 m²' was parsed as 165 m². Must be 65."""
    assert normalize_area("3+1 65 m²") == (65, False)
    assert normalize_area("2+1 51 m²") == (51, False)
    assert normalize_area("1+1 38m2") == (38, False)
    assert normalize_area("2+kk 45 m²") == (45, False)
    assert normalize_area("1+KK 22 m2") == (22, False)


def test_area_multiple_values_takes_last():
    """'dum 89 m², pozemek 544 m²' should return 544 (last)."""
    assert normalize_area("dum 89 m², pozemek 544 m²") == (544, False)


def test_area_unknown():
    assert normalize_area(None) == (None, True)
    assert normalize_area("") == (None, True)
    assert normalize_area("N/A") == (None, True)


# --- Location resolution ---

def test_resolve_location_exact():
    aliases = {"Baška": "baska", "Ostrava-Poruba": "poruba"}
    localities = {"fm": [{"id": "baska", "name": "Baška", "coordinates": [49.64, 18.35]}]}
    assert resolve_location("Baška", aliases, localities) == ("baska", "Baška", (49.64, 18.35))


def test_resolve_location_alias():
    aliases = {"Baska u Frydku-Mistku": "baska"}
    localities = {"fm": [{"id": "baska", "name": "Baška", "coordinates": [49.64, 18.35]}]}
    assert resolve_location("Baska u Frydku-Mistku", aliases, localities) == ("baska", "Baška", (49.64, 18.35))


def test_resolve_location_with_district_suffix():
    aliases = {"Frýdek-Místek": "frydek_mistek"}
    localities = {"fm": [{"id": "frydek_mistek", "name": "Frýdek-Místek", "coordinates": [49.68, 18.34]}]}
    assert resolve_location("Frýdek-Místek, okres Frýdek-Místek", aliases, localities) == (
        "frydek_mistek", "Frýdek-Místek", (49.68, 18.34)
    )


def test_resolve_location_unknown():
    aliases = {}
    localities = {"fm": []}
    assert resolve_location("Neznámá obec", aliases, localities) is None


# --- Strip diacritics ---

def test_strip_diacritics():
    assert strip_diacritics("Frýdek-Místek") == "Frydek-Mistek"
    assert strip_diacritics("Třinec") == "Trinec"
    assert strip_diacritics("Čeladná") == "Celadna"
