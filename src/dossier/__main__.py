"""CLI: python -m src.dossier {add,list,template,build}."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.dossier.favorites import FAVORITES_PATH, KATASTR_TEMPLATE, add_favorite, load_favorites


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.dossier", description="Oblíbené inzeráty a jejich dossiery")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="přidat inzerát do oblíbených")
    p_add.add_argument("url")
    p_add.add_argument("--note")
    sub.add_parser("list", help="vypsat oblíbené")
    sub.add_parser("template", help="vypsat šablonu údajů z katastru")
    p_build = sub.add_parser("build", help="vygenerovat dossiery")
    p_build.add_argument("--out", type=Path)
    p_build.add_argument("--only", type=int, help="jen oblíbený s tímto pořadím (od 0)")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "add":
            fav = add_favorite(args.url, args.note)
            print(f"Uloženo do {FAVORITES_PATH}: {fav['url']}")
            print("Údaje z katastru doplňte ke klíči \"katastr\" (šablona: python -m src.dossier template).")
        elif args.cmd == "list":
            favs = load_favorites()
            if not favs:
                print("Žádné oblíbené. Přidejte: python -m src.dossier add <url>")
            for i, f in enumerate(favs):
                kat = "katastr ✓" if f.get("katastr") else "bez katastru"
                print(f"[{i}] {f['url']}  ({kat}{', ' + f['note'] if f.get('note') else ''})")
        elif args.cmd == "template":
            print(KATASTR_TEMPLATE)
        elif args.cmd == "build":
            from src.dossier.build import DEFAULT_OUT, build_all
            out = args.out or DEFAULT_OUT
            paths = asyncio.run(build_all(out, only=args.only))
            print(f"Hotovo: {len(paths)} dossierů v {out}")
    except ValueError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
