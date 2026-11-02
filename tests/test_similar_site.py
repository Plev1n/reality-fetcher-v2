from src.similar.site import generate_similar_html, build_similar_html
from src.notifications.email_sender import build_similar_email


def _result():
    return {
        "generated": "2026-11-02T20:00:00+00:00",
        "profile": {"slug": "podobne", "name": "Podobné domy", "threshold": 60,
                    "reference_urls": ["https://ref/1"]},
        "new_ids": ["idnes_a"],
        "matches": [
            {"id": "idnes_a", "title": "Prodej domu 135 m² <s> pozemkem", "url": "https://reality.idnes.cz/detail/a/",
             "portal": "idnes", "price": 5500000, "location": "Pržno", "location_id": "przno",
             "added": "2026-11-01", "price_history": [], "area_m2": 1375, "coordinates": None,
             "score": 92, "reasons": ["cena 5,50 mil. ✓"], "match": True, "new": True,
             "owners": ["Tajný Vlastník"],
             "details": {"usable_area": 135, "plot_area": 1375, "disposition": "5+kk", "year_built": 1960,
                         "sewer": "septik / jímka", "gas": None, "condition": "před rekonstrukcí",
                         "penb": "G", "old_price": 5990000}},
            {"id": "b", "title": "Slabý", "url": "https://x/b", "portal": "bazos", "price": 6900000,
             "location": "Frýdek-Místek", "location_id": "frydek_mistek", "added": "2026-10-01",
             "price_history": [], "area_m2": None, "coordinates": None, "score": 41, "reasons": [],
             "match": False, "new": False, "details": None},
        ],
    }


def test_similar_html_contains_matches():
    html = build_similar_html(_result())
    assert "https://reality.idnes.cz/detail/a/" in html
    assert ">92<" in html
    assert "python -m src.dossier add https://reality.idnes.cz/detail/a/" in html
    assert "NOVÉ" in html
    assert "5 990 000" in html  # previous price shown


def test_similar_html_escapes_and_hides_private():
    html = build_similar_html(_result())
    assert "<s> pozemkem" not in html
    assert "&lt;s&gt;" in html
    assert "Tajný Vlastník" not in html


def test_below_threshold_hidden_by_default_attr():
    html = build_similar_html(_result())
    assert 'data-score="41"' in html


def test_generate_writes_file(tmp_path):
    path = generate_similar_html(_result(), site_dir=tmp_path)
    assert path.name == "podobne.html" and path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_similar_email_lists_new_only():
    subject, plain, html = build_similar_email("Podobné domy", [_result()["matches"][0]], "https://dash")
    assert "1" in subject
    assert "Pržno" in plain and "https://reality.idnes.cz/detail/a/" in plain
    assert "Tajný" not in html
