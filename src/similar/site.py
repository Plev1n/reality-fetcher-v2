"""Static dashboard page for similar listings (public: listing data only)."""

from __future__ import annotations

from html import escape
from pathlib import Path

SITE_DIR = Path(__file__).parent.parent.parent / "site"


def _price(p: int | None) -> str:
    return f"{p:,} Kč".replace(",", " ") if p else "Cena na vyžádání"


def _num(n) -> str:
    return f"{n:,}".replace(",", " ") if isinstance(n, int) else "?"


def _card(m: dict) -> str:
    d = m.get("details") or {}
    url = escape(m["url"], quote=True)
    facts = [
        f"užitná <b>{_num(d.get('usable_area'))} m²</b>",
        f"pozemek <b>{_num(d.get('plot_area') or m.get('area_m2'))} m²</b>",
    ]
    if d.get("disposition"):
        facts.append(escape(d["disposition"]))
    if d.get("year_built"):
        facts.append(f"rok {d['year_built']}")
    if d.get("condition"):
        facts.append(escape(d["condition"]))
    if d.get("sewer"):
        facts.append(f"odpad: {escape(d['sewer'])}")
    if d.get("gas") is True:
        facts.append("plyn")
    if d.get("penb"):
        facts.append(f"PENB {escape(d['penb'])}")
    old = d.get("old_price")
    old_html = f' <span class="old">dříve {_price(old)}</span>' if old and old != m.get("price") else ""
    badge = '<span class="badge">NOVÉ</span>' if m.get("new") else ""
    reasons = " · ".join(escape(r) for r in m.get("reasons", []))
    cmd = escape(f"python -m src.dossier add {m['url']}", quote=True)
    cls = "card" + ("" if m.get("match") else " weak")
    return f"""
<article class="{cls}" data-score="{int(m['score'])}">
  <div class="score">{int(m['score'])}</div>
  <div class="body">
    <h2>{badge}<a href="{url}" target="_blank" rel="noopener">{escape(m.get('title') or '')}</a></h2>
    <div class="meta">{escape(m.get('location') or '')} · {escape(m.get('portal') or '')} · od {escape(m.get('added') or '')}</div>
    <div class="price">{_price(m.get('price'))}{old_html}</div>
    <div class="facts">{' · '.join(facts)}</div>
    <div class="reasons">{reasons}</div>
    <button class="fav" data-cmd="{cmd}">⭐ Kopírovat příkaz pro dossier</button>
  </div>
</article>"""


def build_similar_html(result: dict) -> str:
    profile = result.get("profile", {})
    threshold = int(profile.get("threshold", 60))
    matches = result.get("matches", [])
    n_match = sum(1 for m in matches if m.get("match"))
    refs = "".join(
        f'<li><a href="{escape(u, quote=True)}" target="_blank" rel="noopener">{escape(u)}</a></li>'
        for u in profile.get("reference_urls", [])
    )
    cards = "".join(_card(m) for m in matches)
    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(profile.get('name', 'Podobné domy'))} — Reality Monitor</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #fafafa; color: #222; line-height: 1.5; }}
  .header {{ background: #1a1a2e; color: #fff; padding: 16px 24px; }}
  .header h1 {{ margin: 0 0 4px; font-size: 1.4em; }}
  .header .updated, .header details {{ font-size: .85em; opacity: .8; }}
  .header a {{ color: #cfd8ff; }}
  .filters {{ position: sticky; top: 0; background: #fff; border-bottom: 1px solid #ddd; padding: 12px 24px; display: flex; gap: 16px; align-items: center; z-index: 10; }}
  .filters label {{ font-size: .75em; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: .5px; }}
  .container {{ padding: 16px 24px 40px; display: grid; gap: 12px; max-width: 980px; }}
  .card {{ display: flex; gap: 16px; background: #fff; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card.weak {{ opacity: .6; }}
  .score {{ flex: 0 0 56px; height: 56px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 1.2em; background: #e8f5e9; color: #1b5e20; }}
  .card.weak .score {{ background: #eee; color: #555; }}
  .body {{ flex: 1; min-width: 0; }}
  h2 {{ font-size: 1.05em; margin: 0; }}
  h2 a {{ color: #1a1a2e; text-decoration: none; }}
  h2 a:hover {{ text-decoration: underline; }}
  .badge {{ background: #e53935; color: #fff; font-size: .7em; padding: 2px 6px; border-radius: 4px; margin-right: 6px; vertical-align: middle; }}
  .meta, .reasons {{ font-size: .8em; color: #777; }}
  .price {{ font-weight: 700; margin: 4px 0; }}
  .old {{ font-weight: 400; color: #999; text-decoration: line-through; margin-left: 6px; }}
  .facts {{ font-size: .9em; }}
  .fav {{ margin-top: 8px; font: inherit; font-size: .8em; padding: 4px 10px; border: 1px solid #ccc; border-radius: 4px; background: #fff; cursor: pointer; }}
  .fav:hover {{ background: #f5f5f5; }}
  .hidden {{ display: none; }}
</style>
</head>
<body>
<div class="header">
  <h1>{escape(profile.get('name', 'Podobné domy'))}</h1>
  <div class="updated">Aktualizováno {escape(result.get('generated', '')[:16].replace('T', ' '))} UTC · shod: {n_match} · nových: {len(result.get('new_ids', []))} · <a href="index.html">← zpět</a></div>
  <details><summary>Vzorové inzeráty</summary><ul>{refs}</ul></details>
</div>
<div class="filters">
  <label for="min">Min. skóre</label>
  <input id="min" type="range" min="0" max="100" step="5" value="{threshold}">
  <span id="minv">{threshold}</span>
</div>
<main class="container">{cards}
</main>
<script>
  const min = document.getElementById('min'), minv = document.getElementById('minv');
  function apply() {{
    minv.textContent = min.value;
    document.querySelectorAll('.card').forEach(c => c.classList.toggle('hidden', +c.dataset.score < +min.value));
  }}
  min.addEventListener('input', apply); apply();
  document.querySelectorAll('.fav').forEach(b => b.addEventListener('click', () => {{
    navigator.clipboard.writeText(b.dataset.cmd).then(() => {{ b.textContent = '✓ Zkopírováno'; }});
  }}));
</script>
</body>
</html>
"""


def generate_similar_html(result: dict, site_dir: Path = SITE_DIR) -> Path:
    site_dir.mkdir(parents=True, exist_ok=True)
    path = site_dir / f"{result['profile']['slug']}.html"
    path.write_text(build_similar_html(result), encoding="utf-8")
    return path
