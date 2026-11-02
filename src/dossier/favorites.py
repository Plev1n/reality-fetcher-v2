"""Favourite listings – stored locally in private/favorites.json (gitignored, never published)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
FAVORITES_PATH = ROOT / "private" / "favorites.json"

# Filled in by hand from nahlizenidokn.cuzk.cz (the site blocks automated lookups).
KATASTR_TEMPLATE = """{
  "obec": "Název obce",
  "ku_code": 600001,
  "ku_name": "Název katastrálního území",
  "lv": 1,
  "parcels": ["10", "11/2"],
  "owners": ["Příjmení Jméno"],
  "restrictions": {"10": ["Typ omezení přesně jako v nahlížení do KN"]},
  "other_entries": [],
  "price_records": {"10": 0, "11/2": 1}
}"""


def _norm(url: str) -> str:
    return url.strip().rstrip("/")


def load_favorites(path: Path = FAVORITES_PATH) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Poškozený soubor oblíbených {path}: {e}") from e
    if not isinstance(data, list):
        raise ValueError(f"Soubor oblíbených {path} musí obsahovat seznam")
    return data


def save_favorites(favs: list[dict], path: Path = FAVORITES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(favs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def add_favorite(url: str, note: str | None = None, path: Path = FAVORITES_PATH) -> dict:
    favs = load_favorites(path)
    for f in favs:
        if _norm(f["url"]) == _norm(url):
            return f
    fav = {"url": url.strip(), "added": date.today().isoformat(), "note": note, "katastr": None}
    favs.append(fav)
    save_favorites(favs, path)
    return fav
