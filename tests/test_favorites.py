import json
from pathlib import Path

import pytest

from src.dossier.favorites import add_favorite, load_favorites, save_favorites, KATASTR_TEMPLATE


def test_load_missing_returns_empty(tmp_path):
    assert load_favorites(tmp_path / "nope.json") == []


def test_load_corrupt_raises_and_keeps_file(tmp_path):
    p = tmp_path / "f.json"
    p.write_text("{broken")
    with pytest.raises(ValueError, match=str(p)):
        load_favorites(p)
    assert p.read_text() == "{broken"


def test_add_dedup(tmp_path):
    p = tmp_path / "private" / "favorites.json"
    a = add_favorite("https://x/1/", note="pěkný", path=p)
    b = add_favorite("https://x/1", path=p)
    assert a["url"] == b["url"] == "https://x/1/"
    favs = load_favorites(p)
    assert len(favs) == 1 and favs[0]["note"] == "pěkný"
    assert favs[0]["katastr"] is None


def test_save_roundtrip_utf8(tmp_path):
    p = tmp_path / "f.json"
    save_favorites([{"url": "u", "note": "Kunčičky"}], p)
    assert "Kunčičky" in p.read_text(encoding="utf-8")


def test_template_is_valid_json():
    data = json.loads(KATASTR_TEMPLATE)
    assert {"ku_code", "lv", "parcels", "owners", "restrictions"} <= set(data)


def test_gitignore_has_private():
    gi = (Path(__file__).parent.parent / ".gitignore").read_text()
    assert "private/" in gi.splitlines()


def test_cli_corrupt_file_exit_1(tmp_path, monkeypatch, capsys):
    import src.dossier.__main__ as cli
    import src.dossier.favorites as favmod
    p = tmp_path / "f.json"
    p.write_text("{broken")
    monkeypatch.setattr(favmod, "FAVORITES_PATH", p)
    monkeypatch.setattr(cli, "load_favorites", lambda: favmod.load_favorites(p))
    assert cli.main(["list"]) == 1
    assert "Poškozený" in capsys.readouterr().err


def test_dossier_filename_and_municipalities():
    from src.dossier.build import dossier_filename, _municipalities
    from src.similar.details import ListingDetails
    d = ListingDetails(url="u", fetched="x", location="Baška - Kunčičky u Bašky, okres Frýdek-Místek")
    name = dossier_filename({"url": "https://reality.idnes.cz/detail/prodej/dum/baska/6ad877b7046357d39609caed/"}, d)
    assert name == "baska-kuncicky-u-basky-6ad877b7046357d39609caed.md"
    assert _municipalities({"obec": "Baška"}, "Baška - Kunčičky u Bašky, okres Frýdek-Místek") == ["Baška"]
    assert _municipalities(None, "Pržno, okres Frýdek-Místek") == ["Pržno"]


def test_find_listing(tmp_path):
    from src.dossier.build import find_listing
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "fm.json").write_text(json.dumps(
        {"area": {"slug": "fm"}, "listings": [{"id": "a", "url": "https://x/1/"}]}))
    (tmp_path / "data" / "details_cache.json").write_text("{}")
    assert find_listing("https://x/1", tmp_path) == ({"id": "a", "url": "https://x/1/"}, "fm")
    assert find_listing("https://x/2", tmp_path) == (None, None)


def test_out_dir_inside_repo_refused(tmp_path):
    from src.dossier.build import check_out_dir
    root = tmp_path / "repo"
    (root / "site").mkdir(parents=True)
    with pytest.raises(ValueError):
        check_out_dir(root / "site", root)
    with pytest.raises(ValueError):
        check_out_dir(root, root)
    check_out_dir(root / "private" / "dossiers", root)
    check_out_dir(tmp_path / "elsewhere", root)


def test_build_only_out_of_range(tmp_path):
    import asyncio
    from src.dossier.build import build_all
    with pytest.raises(ValueError, match="--only 5"):
        asyncio.run(build_all(tmp_path / "out", favorites=[{"url": "u"}], only=5))
