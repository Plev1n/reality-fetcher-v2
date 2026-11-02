# All people and cadastre values here are fictional.
import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from src.dossier.markdown import render_markdown
from src.dossier.forms import katastr_from_form, katastr_to_form
from src.dossier.favorites import add_favorite, load_favorites, remove_favorite, update_favorite


# --- markdown -------------------------------------------------------------

def test_markdown_basics():
    html = render_markdown("# Nadpis\n\n## Sekce\n\n- **tučně** a [odkaz](https://x.cz/a?b=1&c=2)\n- [ ] úkol\n\n> citace\n")
    assert "<h1>Nadpis</h1>" in html and "<h2>Sekce</h2>" in html
    assert "<strong>tučně</strong>" in html
    assert '<a href="https://x.cz/a?b=1&amp;c=2" target="_blank" rel="noopener">odkaz</a>' in html
    assert '<input type="checkbox" disabled> úkol' in html
    assert "<blockquote>citace</blockquote>" in html


def test_markdown_table_and_code():
    html = render_markdown("| A | B |\n|---|---|\n| 1 | **2** |\n\n```json\n{\"a\": 1}\n```\n")
    assert "<table>" in html and "<th>A</th>" in html and "<td><strong>2</strong></td>" in html
    assert "<pre><code>{&quot;a&quot;: 1}</code></pre>" in html


def test_markdown_escapes_html():
    html = render_markdown("<script>alert(1)</script> [x](javascript:alert(1))")
    assert "<script>" not in html
    assert 'href="javascript' not in html


def test_markdown_bare_url_linked():
    assert '<a href="https://nahlizenidokn.cuzk.cz"' in render_markdown("- Katastr: https://nahlizenidokn.cuzk.cz (ručně)")


# --- forms ----------------------------------------------------------------

FORM = {
    "obec": "Testov", "ku_code": "600001", "ku_name": "Testov", "lv": "1",
    "parcels": "10, 11/2\n12",
    "owners": "Novák Jan\nNováková Jana\n",
    "restrictions": "10: Věcné břemeno (podle listiny); Zákaz zcizení\n11/2: Zástavní právo smluvní",
    "other_entries": "Závazek neumožnit zápis nového zást. práva",
    "price_records": "10: 0\n12: 1",
}


def test_katastr_from_form():
    k = katastr_from_form(FORM)
    assert k == {
        "obec": "Testov", "ku_code": 600001, "ku_name": "Testov", "lv": 1,
        "parcels": ["10", "11/2", "12"],
        "owners": ["Novák Jan", "Nováková Jana"],
        "restrictions": {"10": ["Věcné břemeno (podle listiny)", "Zákaz zcizení"],
                         "11/2": ["Zástavní právo smluvní"]},
        "other_entries": ["Závazek neumožnit zápis nového zást. práva"],
        "price_records": {"10": 0, "12": 1},
    }


def test_katastr_form_roundtrip():
    k = katastr_from_form(FORM)
    assert katastr_from_form(katastr_to_form(k)) == k


def test_katastr_empty_form_is_none():
    assert katastr_from_form({k: "" for k in FORM}) is None


def test_katastr_bad_number_raises():
    with pytest.raises(ValueError, match="ku_code"):
        katastr_from_form({**FORM, "ku_code": "abc"})


# --- favourites -----------------------------------------------------------

def test_update_and_remove_favorite(tmp_path):
    p = tmp_path / "f.json"
    add_favorite("https://x/1", path=p)
    add_favorite("https://x/2", path=p)
    update_favorite(0, path=p, katastr={"lv": 1}, note="pozn")
    assert load_favorites(p)[0]["katastr"] == {"lv": 1} and load_favorites(p)[0]["note"] == "pozn"
    remove_favorite(0, path=p)
    assert [f["url"] for f in load_favorites(p)] == ["https://x/2"]
    with pytest.raises(ValueError):
        remove_favorite(5, path=p)


# --- app ------------------------------------------------------------------

SIMILAR = {"generated": "2026-11-02T20:00:00+00:00",
           "profile": {"slug": "podobne", "name": "Podobné domy", "threshold": 60, "reference_urls": []},
           "new_ids": [], "notified_ids": [],
           "matches": [{"id": "a", "title": "Dům v Testově", "url": "https://reality.example/a",
                        "portal": "idnes", "price": 5500000, "location": "Testov", "score": 91,
                        "reasons": ["cena ✓"], "match": True, "new": False, "added": "2026-11-01",
                        "details": {"usable_area": 130, "plot_area": 1300}}]}


@pytest.fixture
def app(tmp_path):
    from src.dossier.app import make_server

    built = []

    def fake_builder(fav, out_dir):
        path = out_dir / "testov-a.md"
        path.write_text("# Dossier – Dům v Testově\n\n- [ ] úkol\n", encoding="utf-8")
        built.append(fav["url"])
        return path

    server = make_server(0, favorites_path=tmp_path / "private" / "favorites.json",
                         out_dir=tmp_path / "dossiers", similar_loader=lambda: (SIMILAR, "test"),
                         builder=fake_builder)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base, server, built, tmp_path
    server.shutdown()


def _get(url, host=None):
    req = urllib.request.Request(url, headers={"Host": host} if host else {})
    with urllib.request.urlopen(req) as r:
        return r.read().decode()


def _post(url, data, follow=True):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_index_lists_similar(app):
    base, server, _, _ = app
    html = _get(base + "/")
    assert "Dům v Testově" in html and ">91<" in html and "https://reality.example/a" in html


def test_post_without_token_forbidden(app):
    base, _, _, tmp = app
    status, _ = _post(base + "/favorites/add", {"url": "https://reality.example/a"})
    assert status == 403
    assert not (tmp / "private" / "favorites.json").exists()


def test_foreign_host_forbidden(app):
    base, _, _, _ = app
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(base + "/", host="evil.example")
    assert e.value.code == 403


def test_full_flow_add_edit_build(app):
    base, server, built, tmp = app
    token = server.csrf_token
    status, html = _post(base + "/favorites/add", {"url": "https://reality.example/a", "token": token})
    assert status == 200 and "https://reality.example/a" in html
    assert load_favorites(tmp / "private" / "favorites.json")[0]["url"] == "https://reality.example/a"

    form = {**FORM, "note": "pěkný", "token": token}
    status, html = _post(base + "/favorite/0/katastr", form)
    assert status == 200
    fav = load_favorites(tmp / "private" / "favorites.json")[0]
    assert fav["katastr"]["lv"] == 1 and fav["note"] == "pěkný"

    status, html = _post(base + "/favorite/0/build", {"token": token})
    assert status == 200 and built == ["https://reality.example/a"]
    assert "<h1>Dossier – Dům v Testově</h1>" in html
    assert load_favorites(tmp / "private" / "favorites.json")[0]["dossier"] == "testov-a.md"
    assert load_favorites(tmp / "private" / "favorites.json")[0]["title"] == "Dům v Testově"


def test_bad_katastr_shows_error_and_keeps_data(app):
    base, server, _, tmp = app
    token = server.csrf_token
    _post(base + "/favorites/add", {"url": "https://reality.example/a", "token": token})
    status, html = _post(base + "/favorite/0/katastr", {**FORM, "ku_code": "abc", "token": token})
    assert status == 400 and "ku_code" in html
    assert load_favorites(tmp / "private" / "favorites.json")[0]["katastr"] is None


def test_unknown_favorite_404(app):
    base, _, _, _ = app
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(base + "/favorite/7")
    assert e.value.code == 404
