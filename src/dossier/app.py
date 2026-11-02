"""Local mini web app for similar listings, favourites and dossiers.

Run: python -m src.dossier serve   → http://127.0.0.1:8765
Binds to 127.0.0.1 only, rejects foreign Host headers (DNS rebinding) and requires a per-run
token on every POST (CSRF). Everything stays on this computer: private/favorites.json and the
dossier folder outside the repository.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import re
import secrets
import urllib.parse
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.dossier.favorites import (
    FAVORITES_PATH, ROOT, add_favorite, load_favorites, remove_favorite, update_favorite,
)
from src.dossier.forms import katastr_from_form, katastr_to_form
from src.dossier.markdown import render_markdown

REMOTE_SIMILAR = "https://raw.githubusercontent.com/Plev1n/reality-fetcher-v2/main/data/podobne.json"


def default_similar_loader() -> tuple[dict, str]:
    """Latest results from GitHub (CI updates them twice a day), local file as fallback."""
    import httpx
    try:
        r = httpx.get(REMOTE_SIMILAR, timeout=6.0)
        r.raise_for_status()
        return r.json(), "GitHub (aktuální)"
    except Exception:
        path = ROOT / "data" / "podobne.json"
        if path.exists():
            return json.loads(path.read_text()), "lokální data/podobne.json"
        return {"matches": [], "profile": {}}, "žádná data"


def default_builder(fav: dict, out_dir: Path) -> Path:
    from src.dossier.build import build_one
    return asyncio.run(build_one(fav, out_dir))


# --- HTML helpers -----------------------------------------------------------

CSS = """
*,*::before,*::after{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#fafafa;color:#222;line-height:1.5}
header{background:#1a1a2e;color:#fff;padding:12px 24px;display:flex;gap:24px;align-items:center}
header b{font-size:1.15em} header a{color:#cfd8ff;text-decoration:none} header a.on{color:#fff;font-weight:600;border-bottom:2px solid #fff}
main{max-width:980px;padding:16px 24px 48px}
.card{display:flex;gap:16px;background:#fff;border-radius:8px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:12px}
.score{flex:0 0 52px;height:52px;border-radius:50%;display:grid;place-items:center;font-weight:700;background:#e8f5e9;color:#1b5e20}
.card .body{flex:1;min-width:0} .card h3{margin:0;font-size:1.02em} .card h3 a{color:#1a1a2e;text-decoration:none}
.muted{color:#777;font-size:.85em} .price{font-weight:700}
button,.btn{font:inherit;font-size:.85em;padding:5px 12px;border:1px solid #bbb;border-radius:5px;background:#fff;cursor:pointer;color:#222;text-decoration:none;display:inline-block}
button.primary{background:#1a1a2e;color:#fff;border-color:#1a1a2e} button.danger{color:#b71c1c;border-color:#e0a0a0}
form.inline{display:inline}
.tag{font-size:.75em;padding:2px 7px;border-radius:4px;background:#eee;margin-left:6px}
.tag.ok{background:#e8f5e9;color:#1b5e20} .tag.warn{background:#fff3e0;color:#e65100}
.grid{display:grid;grid-template-columns:180px 1fr;gap:8px 12px;align-items:start}
.grid label{font-weight:600;font-size:.85em;padding-top:6px} .grid small{grid-column:2;color:#777;margin-top:-4px}
input[type=text],textarea{width:100%;font:inherit;font-size:.9em;padding:6px 8px;border:1px solid #ccc;border-radius:5px}
textarea{min-height:64px}
.box{background:#fff;border-radius:8px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:16px}
.err{background:#ffebee;color:#b71c1c;padding:8px 12px;border-radius:6px;margin-bottom:12px}
.dossier table{border-collapse:collapse;margin:8px 0;font-size:.9em} .dossier th,.dossier td{border:1px solid #e0e0e0;padding:4px 8px;text-align:left}
.dossier th{background:#f5f5f5} .dossier blockquote{color:#555;border-left:3px solid #ddd;margin:8px 0;padding:2px 12px;font-size:.9em}
.dossier pre{background:#f5f5f5;padding:10px;overflow:auto;font-size:.85em} .dossier li.nested{margin-left:20px}
.toolbar{display:flex;gap:8px;align-items:center;margin:8px 0 16px}
"""


def _page(title: str, body: str, active: str = "") -> bytes:
    nav = "".join(
        f'<a href="{href}" class="{"on" if key == active else ""}">{label}</a>'
        for key, href, label in [("similar", "/", "Podobné domy"), ("favs", "/favorites", "⭐ Oblíbené")]
    )
    return f"""<!DOCTYPE html><html lang="cs"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} – Reality</title>
<style>{CSS}</style></head><body><header><b>Reality – soukromé</b>{nav}</header><main>{body}</main></body></html>""".encode()


def _kc(p) -> str:
    return f"{p:,} Kč".replace(",", " ") if isinstance(p, int) else "cena neuvedena"


class Handler(BaseHTTPRequestHandler):
    server: "AppServer"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    # --- plumbing ---
    def _host_ok(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length") or 0)
        data = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        return {k: v[0] for k, v in data.items()}

    def _hidden(self) -> str:
        return f'<input type="hidden" name="token" value="{self.server.csrf_token}">'

    def _favs(self) -> list[dict]:
        return load_favorites(self.server.favorites_path)

    # --- routing ---
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"Forbidden host")
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/":
                return self._send(200, self.page_similar())
            if path == "/favorites":
                return self._send(200, self.page_favorites())
            m = re.fullmatch(r"/favorite/(\d+)", path)
            if m:
                return self._send(*self.page_favorite(int(m.group(1))))
        except ValueError as e:
            return self._send(500, _page("Chyba", f'<div class="err">{escape(str(e))}</div>'))
        self._send(404, _page("Nenalezeno", "<p>Stránka neexistuje.</p>"))

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, b"Forbidden host")
        form = self._form()
        if not hmac.compare_digest(form.get("token", ""), self.server.csrf_token):
            return self._send(403, _page("Zakázáno", "<p>Neplatný token formuláře. Obnovte stránku.</p>"))
        path = urllib.parse.urlparse(self.path).path
        fp = self.server.favorites_path
        try:
            if path == "/favorites/add":
                url = form.get("url", "").strip()
                if not url.startswith(("http://", "https://")):
                    return self._send(400, _page("Chyba", '<div class="err">Zadejte URL inzerátu.</div>'))
                add_favorite(url, note=form.get("note") or None, path=fp)
                favs = self._favs()
                idx = next(i for i, f in enumerate(favs) if f["url"].rstrip("/") == url.rstrip("/"))
                if form.get("title") and not favs[idx].get("title"):
                    favs[idx]["title"] = form["title"]
                    from src.dossier.favorites import save_favorites
                    save_favorites(favs, fp)
                return self._redirect(f"/favorite/{idx}" if form.get("open") else "/favorites")
            m = re.fullmatch(r"/favorite/(\d+)/(katastr|build|delete)", path)
            if not m:
                return self._send(404, _page("Nenalezeno", "<p>Neznámá akce.</p>"))
            idx, action = int(m.group(1)), m.group(2)
            if not 0 <= idx < len(self._favs()):
                return self._send(404, _page("Nenalezeno", "<p>Oblíbený neexistuje.</p>"))
            if action == "katastr":
                try:
                    kat = katastr_from_form(form)
                except ValueError as e:
                    return self._send(*self.page_favorite(idx, error=str(e), form=form, status=400))
                update_favorite(idx, path=fp, katastr=kat, note=form.get("note") or None)
                return self._redirect(f"/favorite/{idx}")
            if action == "build":
                fav = self._favs()[idx]
                try:
                    self.server.out_dir.mkdir(parents=True, exist_ok=True)
                    out = self.server.builder(fav, self.server.out_dir)
                except Exception as e:
                    return self._send(*self.page_favorite(idx, error=f"Dossier se nepodařilo vytvořit: {e}", status=500))
                update_favorite(idx, path=fp, dossier=Path(out).name)
                if not fav.get("title"):  # favourites added from the CLI have no title yet
                    first = Path(out).read_text(encoding="utf-8").splitlines()[:1]
                    if first and first[0].startswith("# Dossier – "):
                        favs = self._favs()
                        favs[idx]["title"] = first[0].removeprefix("# Dossier – ").strip()
                        from src.dossier.favorites import save_favorites
                        save_favorites(favs, fp)
                return self._redirect(f"/favorite/{idx}#dossier")
            if action == "delete":
                remove_favorite(idx, path=fp)
                return self._redirect("/favorites")
        except ValueError as e:
            return self._send(400, _page("Chyba", f'<div class="err">{escape(str(e))}</div>'))

    # --- pages ---
    def page_similar(self) -> bytes:
        data, source = self.server.similar_loader()
        fav_urls = {f["url"].rstrip("/"): i for i, f in enumerate(self._favs())}
        threshold = (data.get("profile") or {}).get("threshold", 60)
        show_all = "all=1" in (urllib.parse.urlparse(self.path).query or "")
        cards = []
        for m in data.get("matches", []):
            if not show_all and not m.get("match"):
                continue
            d = m.get("details") or {}
            url = m["url"]
            fav_idx = fav_urls.get(url.rstrip("/"))
            if fav_idx is not None:
                action = f'<a class="btn" href="/favorite/{fav_idx}">✓ V oblíbených – otevřít</a>'
            else:
                action = (f'<form class="inline" method="post" action="/favorites/add">{self._hidden()}'
                          f'<input type="hidden" name="url" value="{escape(url, quote=True)}">'
                          f'<input type="hidden" name="title" value="{escape(m.get("title") or "", quote=True)}">'
                          f'<input type="hidden" name="open" value="1">'
                          f'<button class="primary">⭐ Oblíbit a otevřít</button></form>')
            facts = " · ".join(x for x in [
                f"užitná {d.get('usable_area') or '?'} m²",
                f"pozemek {d.get('plot_area') or m.get('area_m2') or '?'} m²",
                d.get("disposition"), f"rok {d['year_built']}" if d.get("year_built") else None,
                d.get("condition"), f"odpad: {d['sewer']}" if d.get("sewer") else None,
                "plyn" if d.get("gas") else None,
            ] if x)
            new = '<span class="tag warn">NOVÉ</span>' if m.get("new") else ""
            cards.append(f"""<div class="card"><div class="score">{int(m.get('score', 0))}</div><div class="body">
<h3><a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{escape(m.get('title') or url)}</a>{new}</h3>
<div class="muted">{escape(m.get('location') or '')} · {escape(m.get('portal') or '')} · od {escape(m.get('added') or '?')}</div>
<div class="price">{_kc(m.get('price'))}</div><div>{escape(facts)}</div>
<div class="muted">{escape(' · '.join(m.get('reasons') or []))}</div><div style="margin-top:8px">{action}</div></div></div>""")
        toggle = ('<a class="btn" href="/">Jen shody</a>' if show_all
                  else f'<a class="btn" href="/?all=1">Zobrazit i pod {threshold} bodů</a>')
        body = (f"<h1>Podobné domy</h1><div class='toolbar'>{toggle}<span class='muted'>Zdroj: {escape(source)} · "
                f"aktualizováno {escape((data.get('generated') or '')[:16].replace('T', ' '))} UTC</span></div>"
                + ("".join(cards) or "<p>Žádné shody.</p>"))
        return _page("Podobné domy", body, "similar")

    def page_favorites(self) -> bytes:
        rows = []
        for i, f in enumerate(self._favs()):
            kat = '<span class="tag ok">katastr ✓</span>' if f.get("katastr") else '<span class="tag warn">bez katastru</span>'
            dos = '<span class="tag ok">dossier ✓</span>' if f.get("dossier") else '<span class="tag">bez dossieru</span>'
            title = f.get("title") or f["url"]
            note = f' – {escape(f["note"])}' if f.get("note") else ""
            rows.append(f'<div class="card"><div class="body"><h3><a href="/favorite/{i}">{escape(title)}</a>{kat}{dos}</h3>'
                        f'<div class="muted">{escape(f["url"])} · přidáno {escape(f.get("added") or "?")}{note}</div></div></div>')
        add = (f'<form method="post" action="/favorites/add" class="toolbar">{self._hidden()}'
               f'<input type="text" name="url" placeholder="URL libovolného inzerátu (iDNES, Sreality, Bazoš…)" required>'
               f'<input type="hidden" name="open" value="1"><button class="primary">Přidat</button></form>')
        body = "<h1>⭐ Oblíbené</h1>" + add + ("".join(rows) or "<p>Zatím nic. Přidejte dům ze stránky Podobné domy.</p>")
        return _page("Oblíbené", body, "favs")

    def page_favorite(self, idx: int, error: str | None = None, form: dict | None = None, status: int = 200):
        favs = self._favs()
        if not 0 <= idx < len(favs):
            return 404, _page("Nenalezeno", "<p>Oblíbený neexistuje.</p>", "favs")
        fav = favs[idx]
        values = form if form is not None else {**katastr_to_form(fav.get("katastr")), "note": fav.get("note") or ""}
        h = self._hidden()

        def field(name, label, help_="", area=False):
            v = escape(values.get(name, ""), quote=True)
            inp = (f'<textarea name="{name}" id="{name}">{v}</textarea>' if area
                   else f'<input type="text" name="{name}" id="{name}" value="{v}">')
            return f'<label for="{name}">{label}</label>{inp}' + (f"<small>{help_}</small>" if help_ else "")

        err = f'<div class="err">{escape(error)}</div>' if error else ""
        kat_form = f"""<div class="box"><h2>Údaje z katastru</h2>
<p class="muted">Najděte dům na <a href="https://nahlizenidokn.cuzk.cz" target="_blank" rel="noopener">nahlizenidokn.cuzk.cz</a>
(obec + č. p., nebo mapa) → <i>Seznam nemovitostí na LV</i> a opište údaje. Zůstanou jen v tomto počítači.</p>
<form method="post" action="/favorite/{idx}/katastr">{h}<div class="grid">
{field("note", "Poznámka")}
{field("obec", "Obec", "pro hledání zakázek na kanalizaci (např. Baška)")}
{field("ku_name", "Katastrální území")}
{field("ku_code", "Kód k. ú.", "číslo v hranatých závorkách, např. Testov [600001]")}
{field("lv", "Číslo LV")}
{field("parcels", "Parcely", "oddělené čárkou nebo řádky; stavební parcely jako „st. 12“", area=True)}
{field("owners", "Vlastníci", "jeden na řádek, jak je v katastru: Příjmení Jméno", area=True)}
{field("restrictions", "Omezení vlastnického práva", "parcela: typ; typ — např. „10: Zástavní právo smluvní“", area=True)}
{field("other_entries", "Jiné zápisy", "jeden na řádek", area=True)}
{field("price_records", "Cenové údaje", "parcela: počet řízení s cenou — např. „10: 1“", area=True)}
</div><div class="toolbar"><button class="primary">Uložit údaje</button></div></form></div>"""

        dossier_html = ""
        if fav.get("dossier"):
            p = self.server.out_dir / fav["dossier"]
            if p.exists():
                dossier_html = f'<div class="box dossier" id="dossier">{render_markdown(p.read_text(encoding="utf-8"))}</div>'
        build = (f'<form class="inline" method="post" action="/favorite/{idx}/build">{h}'
                 f'<button class="primary" onclick="this.textContent=\'Generuji… (10–30 s)\'">'
                 f'{"Přegenerovat" if fav.get("dossier") else "Vygenerovat"} dossier</button></form>')
        delete = (f'<form class="inline" method="post" action="/favorite/{idx}/delete" '
                  f'onsubmit="return confirm(\'Odebrat z oblíbených?\')">{h}<button class="danger">Odebrat</button></form>')
        head = (f'<h1>{escape(fav.get("title") or "Oblíbený inzerát")}</h1>'
                f'<p><a href="{escape(fav["url"], quote=True)}" target="_blank" rel="noopener">{escape(fav["url"])}</a></p>'
                f'<div class="toolbar">{build}{delete}</div>')
        return status, _page("Oblíbený", err + head + dossier_html + kat_form, "favs")


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, favorites_path: Path, out_dir: Path, similar_loader, builder):
        super().__init__(addr, Handler)
        self.favorites_path = favorites_path
        self.out_dir = out_dir
        self.similar_loader = similar_loader
        self.builder = builder
        self.csrf_token = secrets.token_urlsafe(24)


def make_server(port: int = 8765, favorites_path: Path = FAVORITES_PATH, out_dir: Path | None = None,
                similar_loader=default_similar_loader, builder=default_builder) -> AppServer:
    from src.dossier.build import DEFAULT_OUT, check_out_dir
    out_dir = out_dir or DEFAULT_OUT
    if builder is default_builder:
        check_out_dir(out_dir)
    return AppServer(("127.0.0.1", port), favorites_path, out_dir, similar_loader, builder)


def serve(port: int = 8765, open_browser: bool = True) -> None:
    server = make_server(port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Reality – soukromé: {url}  (Ctrl+C ukončí)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUkončeno.")
    finally:
        server.server_close()
