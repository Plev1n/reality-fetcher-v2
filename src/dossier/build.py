"""Gather all sources for favourites and write Markdown dossiers outside the repository."""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
from pathlib import Path

import httpx

from src.dossier.favorites import ROOT, load_favorites
from src.dossier.history import history_pool, match_history
from src.dossier.katastr import parcel_areas
from src.dossier.market import market_stats
from src.dossier.municipality import sewer_tenders
from src.dossier.registries import ares_lookup, isir_lookup
from src.dossier.report import build_report
from src.pipeline.normalizer import strip_diacritics
from src.scrapers.base import BaseScraper
from src.similar.details import fetch_details

DEFAULT_OUT = Path(os.environ.get(
    "REALITY_DOSSIER_DIR", Path.home() / "Projects" / "personal" / "reality-research" / "dossiers"))


def _norm(url: str) -> str:
    return url.strip().rstrip("/")


def find_listing(url: str, repo_root: Path = ROOT) -> tuple[dict | None, str | None]:
    """Return (listing, area_slug) from data/*.json matching the URL."""
    for path in sorted((repo_root / "data").glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if not isinstance(data, dict) or "area" not in data:
            continue
        for l in data.get("listings", []):
            if _norm(l.get("url", "")) == _norm(url):
                return l, path.stem
    return None, None


async def _safe(coro):
    try:
        return await coro
    except Exception as e:  # reported in the dossier as "nepodařilo se ověřit"
        return e


def _municipalities(kat: dict | None, location: str | None) -> list[str]:
    names = []
    if kat and kat.get("obec"):
        names.append(kat["obec"])
    if location:
        names.append(location.split(",")[0].split(" - ")[0].strip())
    return list(dict.fromkeys(n for n in names if n))


async def gather(fav: dict, client: httpx.AsyncClient, repo_root: Path = ROOT, area_slug_default: str = "fm"):
    details = await fetch_details(fav["url"], client)
    listing, area_slug = find_listing(fav["url"], repo_root)
    area_slug = area_slug or area_slug_default
    if listing is None:
        listing = {"id": None, "url": fav["url"], "type": "dum", "price": details.price,
                   "location": details.location, "location_id": None, "title": details.title}
    kat = fav.get("katastr")
    ctx: dict = {"listing": listing}

    def _history():
        pool = history_pool(repo_root, area_slug)
        name = (listing.get("location") or details.location or "").split(",")[0].split(" - ")[-1]
        return match_history(listing, name, details.plot_area, pool)

    try:
        ctx["history"] = await asyncio.to_thread(_history)
    except Exception as e:
        ctx["history"] = e

    try:
        area_data = json.loads((repo_root / "data" / f"{area_slug}.json").read_text())
        ctx["market"] = market_stats(area_data, listing.get("location_id"))
    except Exception as e:
        ctx["market"] = e

    tenders: list | Exception = []
    for name in _municipalities(kat, listing.get("location") or details.location):
        res = await _safe(sewer_tenders(name, client))
        if isinstance(res, Exception):
            tenders = res
            break
        tenders.extend(t for t in res if t["id"] not in {x["id"] for x in tenders})
    ctx["tenders"] = tenders

    if kat:
        ctx["parcel_areas"] = await _safe(parcel_areas(kat["ku_code"], kat.get("parcels") or [], client))
        ares, isir = {}, {}
        for owner in kat.get("owners") or []:
            a = await _safe(ares_lookup(owner, client))
            i = await _safe(isir_lookup(owner, client))
            if isinstance(a, Exception):
                ares = a
            elif isinstance(ares, dict):
                ares[owner] = a
            if isinstance(i, Exception):
                isir = i
            elif isinstance(isir, dict):
                isir[owner] = i
        ctx["ares"], ctx["isir"] = ares, isir
    return details, ctx


def check_out_dir(out_dir: Path, repo_root: Path = ROOT) -> None:
    """Dossiers contain owner data: never write them where CI could commit/publish them."""
    out, root = out_dir.expanduser().resolve(), repo_root.resolve()
    if (out == root or root in out.parents) and not (out == root / "private" or (root / "private") in out.parents):
        raise ValueError(f"Dossiery nelze ukládat do repozitáře ({out}); použijte složku mimo něj nebo private/")


def dossier_filename(fav: dict, details) -> str:
    loc = strip_diacritics((details.location or "inzerat").split(",")[0]).lower()
    loc = re.sub(r"[^a-z0-9]+", "-", loc).strip("-") or "inzerat"
    tail = re.sub(r"[^A-Za-z0-9]+", "", _norm(fav["url"]).split("/")[-1])[-24:] or "x"
    return f"{loc}-{tail}.md"


async def build_all(out_dir: Path = DEFAULT_OUT, favorites: list[dict] | None = None,
                    only: int | None = None) -> list[Path]:
    check_out_dir(out_dir)
    favs = favorites if favorites is not None else load_favorites()
    if only is not None:
        if not 0 <= only < len(favs):
            raise ValueError(f"--only {only}: oblíbených je {len(favs)} (indexy 0–{len(favs) - 1})")
        favs = [favs[only]]
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[tuple[Path, str, dict]] = []
    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True,
                                 headers={"User-Agent": random.choice(BaseScraper.USER_AGENTS)}) as client:
        for fav in favs:
            details, ctx = await gather(fav, client)
            path = out_dir / dossier_filename(fav, details)
            path.write_text(build_report(fav, details, ctx), encoding="utf-8")
            written.append((path, details.title or fav["url"], ctx))
            print(f"  ✓ {path}")
    index = ["# Dossiery oblíbených", ""]
    for path, title, ctx in written:
        price = ctx["listing"].get("price")
        index.append(f"- [{title}]({path.name})" + (f" – {price:,} Kč".replace(",", " ") if price else ""))
    (out_dir / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return [p for p, _, _ in written]
