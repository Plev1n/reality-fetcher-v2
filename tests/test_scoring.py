import json
from pathlib import Path

from src.similar.details import ListingDetails
from src.similar.scoring import score_listing

PROFILE = json.loads((Path(__file__).parent.parent / "config" / "profiles.json").read_text())[0]


def _listing(price, loc="przno", area=None):
    return {"id": "x", "type": "dum", "price": price, "location_id": loc, "area_m2": area, "status": "active"}


def _det(usable, plot, rooms):
    return ListingDetails(url="u", fetched="2026-11-02", usable_area=usable, plot_area=plot, rooms=rooms)


def test_reference_przno_scores_high():
    score, reasons = score_listing(_listing(5500000), _det(135, 1375, 5), PROFILE)
    assert score >= 90
    assert any("pozemek" in r for r in reasons)


def test_reference_kuncicky_scores_high():
    score, _ = score_listing(_listing(5990000, "kuncicky_u_basky"), _det(110, 1291, 4), PROFILE)
    assert score >= 85


def test_out_of_range_low():
    score, _ = score_listing(_listing(9500000, "frydek_mistek"), _det(300, 400, 7), PROFILE)
    assert score < 40


def test_missing_details_half_weight():
    score, _ = score_listing(_listing(5500000), None, PROFILE)
    assert 50 <= score <= 75


def test_plot_from_listing_when_details_missing():
    with_plot, _ = score_listing(_listing(5500000, area=1300), None, PROFILE)
    without, _ = score_listing(_listing(5500000), None, PROFILE)
    assert with_plot > without


def test_unknown_price_is_half():
    s1, _ = score_listing(_listing(None), _det(135, 1375, 5), PROFILE)
    s2, _ = score_listing(_listing(5500000), _det(135, 1375, 5), PROFILE)
    assert s1 < s2 and s1 >= 70


def test_edge_linear_falloff():
    mid, _ = score_listing(_listing(6750000), _det(135, 1375, 5), PROFILE)
    ideal, _ = score_listing(_listing(6000000), _det(135, 1375, 5), PROFILE)
    out, _ = score_listing(_listing(7100000), _det(135, 1375, 5), PROFILE)
    assert ideal > mid > out


def test_rooms_label_grammar():
    _, reasons = score_listing(_listing(5500000), _det(110, 1291, 4), PROFILE)
    assert "4 pokoje ✓" in reasons
