"""Load JSON configuration files."""

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR = Path(__file__).parent.parent / "data"


def load_areas() -> list[dict]:
    return json.loads((CONFIG_DIR / "areas.json").read_text())


def load_localities() -> dict[str, list[dict]]:
    return json.loads((CONFIG_DIR / "localities.json").read_text())


def load_aliases() -> dict[str, str]:
    return json.loads((CONFIG_DIR / "aliases.json").read_text())


def load_blacklists() -> dict[str, list[str]]:
    return json.loads((CONFIG_DIR / "blacklist.json").read_text())


def load_url_patterns() -> dict[str, list[str]]:
    return json.loads((CONFIG_DIR / "url_patterns.json").read_text())


def load_portal_health() -> dict:
    return json.loads((DATA_DIR / "portal_health.json").read_text())


def save_portal_health(health: dict) -> None:
    (DATA_DIR / "portal_health.json").write_text(
        json.dumps(health, indent=2, ensure_ascii=False) + "\n"
    )


def load_area_data(slug: str) -> dict:
    path = DATA_DIR / f"{slug}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"generated": None, "area": {"slug": slug}, "listings": []}


def save_area_data(slug: str, data: dict) -> None:
    (DATA_DIR / f"{slug}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    )
