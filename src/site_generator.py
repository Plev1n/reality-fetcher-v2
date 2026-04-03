"""Generate self-contained static HTML dashboard files from JSON data."""

import json
from pathlib import Path

SITE_DIR = Path(__file__).parent.parent / "site"


def _format_price(price: int | None, unknown: bool = False) -> str:
    """Format price Czech-style with spaces: 7 980 000 Kč."""
    if unknown or price is None:
        return "Cena na vyžádání"
    s = str(price)
    parts = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    return " ".join(reversed(parts)) + " Kč"


def generate_html(area_config: dict, data: dict) -> None:
    """Generate a self-contained HTML dashboard for one area.

    Args:
        area_config: Area configuration dict (slug, name, types, ...).
        data: Full area data dict (from data/{slug}.json) with generated, area, listings.
    """
    slug = area_config["slug"]
    name = area_config["name"]
    types = area_config.get("types", [])
    show_type_filter = len(types) > 1

    # Embed data as JSON for client-side filtering
    data_json = json.dumps(data, ensure_ascii=False)

    html = _build_html(name, slug, show_type_filter, types, data_json)

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / f"{slug}.html").write_text(html, encoding="utf-8")


def _build_html(
    name: str,
    slug: str,
    show_type_filter: bool,
    types: list[str],
    data_json: str,
) -> str:
    type_options = ""
    if show_type_filter:
        type_options = '<option value="">Vše</option>'
        type_labels = {"dum": "Dům", "pozemek": "Pozemek", "byt": "Byt"}
        for t in types:
            label = type_labels.get(t, t)
            type_options += f'<option value="{t}">{label}</option>'

    type_filter_html = ""
    if show_type_filter:
        type_filter_html = f"""
        <div class="filter-group">
          <label for="filter-type">Typ</label>
          <select id="filter-type">{type_options}</select>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} — Reality Monitor</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0; padding: 0;
      background: #fafafa; color: #222;
      line-height: 1.5;
    }}
    .header {{
      background: #1a1a2e; color: #fff;
      padding: 16px 24px;
    }}
    .header h1 {{
      margin: 0 0 4px 0; font-size: 1.4em;
    }}
    .header .updated {{
      font-size: 0.85em; opacity: 0.7;
    }}
    .stats {{
      display: flex; gap: 16px; margin-top: 8px; flex-wrap: wrap;
    }}
    .stat {{
      background: rgba(255,255,255,0.1);
      padding: 4px 12px; border-radius: 6px;
      font-size: 0.85em;
    }}
    .stat strong {{ font-size: 1.1em; }}

    .filters {{
      position: sticky; top: 0; z-index: 100;
      background: #fff; border-bottom: 1px solid #ddd;
      padding: 12px 24px;
      display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end;
    }}
    .filter-group {{
      display: flex; flex-direction: column; gap: 2px;
    }}
    .filter-group label {{
      font-size: 0.75em; font-weight: 600; color: #666;
      text-transform: uppercase; letter-spacing: 0.5px;
    }}
    .filter-group select,
    .filter-group input {{
      padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px;
      font-size: 0.9em; font-family: inherit;
    }}
    .filter-group input[type="number"] {{
      width: 100px;
    }}
    .range-inputs {{
      display: flex; gap: 4px; align-items: center;
    }}
    .range-sep {{ color: #999; }}

    .container {{
      padding: 0 24px 40px;
    }}

    table {{
      width: 100%; border-collapse: collapse;
      margin-top: 16px; background: #fff;
      border-radius: 8px; overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    thead th {{
      background: #f5f5f5; padding: 10px 12px;
      text-align: left; font-size: 0.8em;
      text-transform: uppercase; letter-spacing: 0.5px;
      color: #555; border-bottom: 2px solid #e0e0e0;
      white-space: nowrap;
    }}
    tbody td {{
      padding: 10px 12px; border-bottom: 1px solid #f0f0f0;
      font-size: 0.9em; vertical-align: middle;
    }}
    tbody tr:hover {{
      background: #f8f8ff;
    }}

    .badge {{
      display: inline-block; padding: 2px 8px;
      border-radius: 4px; font-size: 0.75em;
      font-weight: 600; text-transform: uppercase;
    }}
    .badge-dum {{ background: #e3f2fd; color: #1565c0; }}
    .badge-pozemek {{ background: #e8f5e9; color: #2e7d32; }}
    .badge-byt {{ background: #fff3e0; color: #e65100; }}
    .badge-new {{
      background: #43a047; color: #fff;
      margin-left: 6px; font-size: 0.7em;
      vertical-align: middle;
    }}

    .price-changed {{
      background: #fff9c4 !important;
    }}
    .price-change {{
      font-size: 0.8em; white-space: nowrap;
    }}
    .price-drop {{ color: #2e7d32; }}
    .price-rise {{ color: #c62828; }}

    .location-link {{
      color: #1565c0; text-decoration: none;
    }}
    .location-link:hover {{ text-decoration: underline; }}

    .portal-link {{
      color: #1565c0; text-decoration: none;
      font-size: 0.85em;
    }}
    .portal-link:hover {{ text-decoration: underline; }}

    .removed-section {{
      margin-top: 32px;
    }}
    .removed-toggle {{
      cursor: pointer; user-select: none;
      padding: 12px 0; font-size: 1.1em; font-weight: 600;
      color: #666; display: flex; align-items: center; gap: 8px;
    }}
    .removed-toggle:hover {{ color: #333; }}
    .removed-toggle .arrow {{
      transition: transform 0.2s;
      display: inline-block;
    }}
    .removed-toggle .arrow.open {{
      transform: rotate(90deg);
    }}
    .removed-content {{ display: none; }}
    .removed-content.open {{ display: block; }}

    .removed-row td {{
      text-decoration: line-through;
      color: #999;
    }}
    .removed-row .badge {{ opacity: 0.5; }}

    .no-results {{
      text-align: center; padding: 40px;
      color: #999; font-size: 1.1em;
    }}

    .price-unknown {{
      font-style: italic; color: #888;
    }}

    @media (max-width: 900px) {{
      .filters {{ padding: 10px 12px; gap: 8px; }}
      .container {{ padding: 0 8px 24px; }}
      table {{ font-size: 0.85em; }}
      thead th, tbody td {{ padding: 8px 6px; }}
      .filter-group input[type="number"] {{ width: 80px; }}
    }}
    @media (max-width: 600px) {{
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>

<div class="header">
  <h1>{name}</h1>
  <div class="updated" id="updated"></div>
  <div class="stats" id="stats"></div>
</div>

<div class="filters">
  <div class="filter-group">
    <label for="filter-status">Status</label>
    <select id="filter-status">
      <option value="">Vše</option>
      <option value="new">Nové</option>
      <option value="price_changed">Změna ceny</option>
      <option value="removed">Smazané</option>
    </select>
  </div>{type_filter_html}
  <div class="filter-group">
    <label for="filter-location">Lokalita</label>
    <select id="filter-location">
      <option value="">Vše</option>
    </select>
  </div>
  <div class="filter-group">
    <label>Cena</label>
    <div class="range-inputs">
      <input type="number" id="filter-price-min" placeholder="od">
      <span class="range-sep">–</span>
      <input type="number" id="filter-price-max" placeholder="do">
    </div>
  </div>
  <div class="filter-group">
    <label>Plocha (m²)</label>
    <div class="range-inputs">
      <input type="number" id="filter-area-min" placeholder="od">
      <span class="range-sep">–</span>
      <input type="number" id="filter-area-max" placeholder="do">
    </div>
  </div>
  <div class="filter-group">
    <label for="filter-sort">Řazení</label>
    <select id="filter-sort">
      <option value="added_desc">Datum přidání ↓</option>
      <option value="added_asc">Datum přidání ↑</option>
      <option value="price_asc">Cena ↑</option>
      <option value="price_desc">Cena ↓</option>
      <option value="ppm2_asc">Cena/m² ↑</option>
      <option value="ppm2_desc">Cena/m² ↓</option>
      <option value="area_asc">Plocha ↑</option>
      <option value="area_desc">Plocha ↓</option>
    </select>
  </div>
</div>

<div class="container">
  <table>
    <thead>
      <tr>
        <th>Typ</th>
        <th>Lokalita</th>
        <th>Plocha</th>
        <th>Cena</th>
        <th>Cena/m²</th>
        <th>Změna ceny</th>
        <th>Přidáno</th>
        <th>Odkaz</th>
      </tr>
    </thead>
    <tbody id="listing-body"></tbody>
  </table>
  <div id="no-results" class="no-results" style="display:none;">Žádné výsledky pro zvolené filtry.</div>

  <div class="removed-section">
    <div class="removed-toggle" id="removed-toggle" style="display:none;">
      <span class="arrow" id="removed-arrow">&#9654;</span>
      Smazané inzeráty (<span id="removed-count">0</span>)
    </div>
    <div class="removed-content" id="removed-content">
      <table>
        <thead>
          <tr>
            <th>Typ</th>
            <th>Lokalita</th>
            <th>Plocha</th>
            <th>Cena</th>
            <th>Cena/m²</th>
            <th>Smazáno</th>
            <th>Odkaz</th>
          </tr>
        </thead>
        <tbody id="removed-body"></tbody>
      </table>
    </div>
  </div>
</div>

<script>const DATA = {data_json};</script>
<script>
(function() {{
  const SLUG = "{slug}";
  const STORAGE_KEY = "rf2_filters_" + SLUG;

  const typeLabels = {{ dum: "Dům", pozemek: "Pozemek", byt: "Byt" }};
  const typeBadgeClass = {{ dum: "badge-dum", pozemek: "badge-pozemek", byt: "badge-byt" }};

  // --- Helpers ---
  function formatPrice(price, unknown) {{
    if (unknown || price == null) return '<span class="price-unknown">Cena na vyžádání</span>';
    return price.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, " ") + " Kč";
  }}

  function formatArea(m2) {{
    if (m2 == null) return "—";
    return m2.toLocaleString("cs-CZ") + " m²";
  }}

  function formatDate(d) {{
    if (!d) return "—";
    const parts = d.split("-");
    return parts[2] + "." + parts[1] + "." + parts[0];
  }}

  function mapsLink(location, coords) {{
    if (coords && coords.length === 2) {{
      return '<a class="location-link" href="https://maps.google.com/?q=' +
        coords[0] + ',' + coords[1] + '" target="_blank" rel="noopener">' +
        escHtml(location) + '</a>';
    }}
    return escHtml(location);
  }}

  function escHtml(s) {{
    if (!s) return "";
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }}

  function getPriceChange(listing) {{
    const hist = listing.price_history;
    if (!hist || hist.length < 2) return null;
    const prev = hist[hist.length - 2].price;
    const curr = hist[hist.length - 1].price;
    if (prev == null || curr == null || prev === curr) return null;
    const pct = ((curr - prev) / prev) * 100;
    return {{ prev: prev, curr: curr, pct: pct }};
  }}

  function isNew(listing) {{
    if (!DATA.generated || !listing.added) return false;
    const genDate = DATA.generated.substring(0, 10);
    return listing.added === genDate;
  }}

  // --- Populate location dropdown ---
  function populateLocations() {{
    const sel = document.getElementById("filter-location");
    const locs = new Set();
    (DATA.listings || []).forEach(function(l) {{
      if (l.location && l.status === "active") locs.add(l.location);
    }});
    Array.from(locs).sort(function(a,b) {{ return a.localeCompare(b, "cs"); }}).forEach(function(loc) {{
      const opt = document.createElement("option");
      opt.value = loc; opt.textContent = loc;
      sel.appendChild(opt);
    }});
  }}

  // --- Stats ---
  function updateStats() {{
    const listings = DATA.listings || [];
    const active = listings.filter(function(l) {{ return l.status === "active"; }});
    const newToday = active.filter(isNew);
    const priceChanged = active.filter(function(l) {{ return getPriceChange(l) !== null; }});
    const removed = listings.filter(function(l) {{ return l.status === "removed"; }});

    document.getElementById("stats").innerHTML =
      '<div class="stat"><strong>' + active.length + '</strong> aktivních</div>' +
      '<div class="stat"><strong>' + newToday.length + '</strong> nových</div>' +
      '<div class="stat"><strong>' + priceChanged.length + '</strong> změn ceny</div>' +
      '<div class="stat"><strong>' + removed.length + '</strong> smazaných</div>';

    if (DATA.generated) {{
      const d = new Date(DATA.generated);
      document.getElementById("updated").textContent = "Aktualizováno: " +
        d.toLocaleString("cs-CZ", {{ day: "numeric", month: "numeric", year: "numeric",
          hour: "2-digit", minute: "2-digit" }});
    }}
  }}

  // --- Filter state ---
  function getFilterState() {{
    return {{
      status: document.getElementById("filter-status").value,
      type: document.getElementById("filter-type") ? document.getElementById("filter-type").value : "",
      location: document.getElementById("filter-location").value,
      priceMin: document.getElementById("filter-price-min").value,
      priceMax: document.getElementById("filter-price-max").value,
      areaMin: document.getElementById("filter-area-min").value,
      areaMax: document.getElementById("filter-area-max").value,
      sort: document.getElementById("filter-sort").value
    }};
  }}

  function setFilterState(state) {{
    if (!state) return;
    if (state.status) document.getElementById("filter-status").value = state.status;
    var typeEl = document.getElementById("filter-type");
    if (typeEl && state.type) typeEl.value = state.type;
    if (state.location) document.getElementById("filter-location").value = state.location;
    if (state.priceMin) document.getElementById("filter-price-min").value = state.priceMin;
    if (state.priceMax) document.getElementById("filter-price-max").value = state.priceMax;
    if (state.areaMin) document.getElementById("filter-area-min").value = state.areaMin;
    if (state.areaMax) document.getElementById("filter-area-max").value = state.areaMax;
    if (state.sort) document.getElementById("filter-sort").value = state.sort;
  }}

  function saveFilters() {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(getFilterState())); }} catch(e) {{}}
  }}

  function loadFilters() {{
    try {{
      var s = localStorage.getItem(STORAGE_KEY);
      if (s) setFilterState(JSON.parse(s));
    }} catch(e) {{}}
  }}

  // --- Filter + Sort + Render ---
  function filterAndSort() {{
    var state = getFilterState();
    var listings = (DATA.listings || []).slice();

    // Separate active and removed
    var active = listings.filter(function(l) {{ return l.status === "active"; }});
    var removed = listings.filter(function(l) {{ return l.status === "removed"; }});

    // Apply filters to active listings
    var filtered = active;

    // Status filter
    if (state.status === "new") {{
      filtered = filtered.filter(isNew);
    }} else if (state.status === "price_changed") {{
      filtered = filtered.filter(function(l) {{ return getPriceChange(l) !== null; }});
    }} else if (state.status === "removed") {{
      // Show removed instead
      filtered = [];
    }}

    // Type filter
    if (state.type) {{
      filtered = filtered.filter(function(l) {{ return l.type === state.type; }});
    }}

    // Location filter
    if (state.location) {{
      filtered = filtered.filter(function(l) {{ return l.location === state.location; }});
    }}

    // Price range (pass price_unknown through)
    var priceMin = state.priceMin ? parseInt(state.priceMin) : null;
    var priceMax = state.priceMax ? parseInt(state.priceMax) : null;
    if (priceMin != null) {{
      filtered = filtered.filter(function(l) {{ return l.price_unknown || (l.price != null && l.price >= priceMin); }});
    }}
    if (priceMax != null) {{
      filtered = filtered.filter(function(l) {{ return l.price_unknown || (l.price != null && l.price <= priceMax); }});
    }}

    // Area range
    var areaMin = state.areaMin ? parseInt(state.areaMin) : null;
    var areaMax = state.areaMax ? parseInt(state.areaMax) : null;
    if (areaMin != null) {{
      filtered = filtered.filter(function(l) {{ return l.area_m2 != null && l.area_m2 >= areaMin; }});
    }}
    if (areaMax != null) {{
      filtered = filtered.filter(function(l) {{ return l.area_m2 != null && l.area_m2 <= areaMax; }});
    }}

    // Sort
    var sortParts = state.sort.split("_");
    var sortKey = sortParts[0];
    var sortDir = sortParts[1] === "asc" ? 1 : -1;

    filtered.sort(function(a, b) {{
      var va, vb;
      if (sortKey === "added") {{
        va = a.added || ""; vb = b.added || "";
        return va < vb ? -sortDir : va > vb ? sortDir : 0;
      }} else if (sortKey === "price") {{
        va = a.price != null ? a.price : (sortDir === 1 ? Infinity : -Infinity);
        vb = b.price != null ? b.price : (sortDir === 1 ? Infinity : -Infinity);
      }} else if (sortKey === "ppm2") {{
        va = a.price_per_m2 != null ? a.price_per_m2 : (sortDir === 1 ? Infinity : -Infinity);
        vb = b.price_per_m2 != null ? b.price_per_m2 : (sortDir === 1 ? Infinity : -Infinity);
      }} else if (sortKey === "area") {{
        va = a.area_m2 != null ? a.area_m2 : (sortDir === 1 ? Infinity : -Infinity);
        vb = b.area_m2 != null ? b.area_m2 : (sortDir === 1 ? Infinity : -Infinity);
      }} else {{
        return 0;
      }}
      return (va - vb) * sortDir;
    }});

    // Render active
    renderActive(filtered);

    // Render removed (always, but in collapsed section)
    renderRemoved(removed, state.status === "removed");

    saveFilters();
  }}

  function renderActive(listings) {{
    var tbody = document.getElementById("listing-body");
    var noResults = document.getElementById("no-results");

    if (listings.length === 0) {{
      tbody.innerHTML = "";
      noResults.style.display = "block";
      return;
    }}
    noResults.style.display = "none";

    var html = "";
    listings.forEach(function(l) {{
      var change = getPriceChange(l);
      var rowClass = change ? ' class="price-changed"' : '';
      var newBadge = isNew(l) ? ' <span class="badge badge-new">NEW</span>' : '';

      var changeHtml = "—";
      if (change) {{
        var dir = change.pct < 0 ? "drop" : "rise";
        var arrow = change.pct < 0 ? "&#8595;" : "&#8593;";
        var sign = change.pct > 0 ? "+" : "";
        changeHtml = '<span class="price-change price-' + dir + '">' +
          arrow + " " + sign + change.pct.toFixed(1) + "%</span>";
      }}

      html += "<tr" + rowClass + ">" +
        "<td><span class='badge " + (typeBadgeClass[l.type] || "") + "'>" +
          (typeLabels[l.type] || l.type) + "</span>" + newBadge + "</td>" +
        "<td>" + mapsLink(l.location, l.coordinates) + "</td>" +
        "<td>" + formatArea(l.area_m2) + "</td>" +
        "<td>" + formatPrice(l.price, l.price_unknown) + "</td>" +
        "<td>" + formatPrice(l.price_per_m2, l.price_unknown) + "</td>" +
        "<td>" + changeHtml + "</td>" +
        "<td>" + formatDate(l.added) + "</td>" +
        "<td><a class='portal-link' href='" + escHtml(l.url) + "' target='_blank' rel='noopener'>" +
          escHtml(l.portal) + "</a></td>" +
        "</tr>";
    }});
    tbody.innerHTML = html;
  }}

  function renderRemoved(listings, forceShow) {{
    var toggle = document.getElementById("removed-toggle");
    var body = document.getElementById("removed-body");
    var countEl = document.getElementById("removed-count");

    if (listings.length === 0) {{
      toggle.style.display = "none";
      return;
    }}
    toggle.style.display = "flex";
    countEl.textContent = listings.length;

    // Sort removed by removed_date desc
    listings.sort(function(a, b) {{
      var da = a.removed_date || ""; var db = b.removed_date || "";
      return da < db ? 1 : da > db ? -1 : 0;
    }});

    var html = "";
    listings.forEach(function(l) {{
      html += '<tr class="removed-row">' +
        "<td><span class='badge " + (typeBadgeClass[l.type] || "") + "'>" +
          (typeLabels[l.type] || l.type) + "</span></td>" +
        "<td>" + escHtml(l.location) + "</td>" +
        "<td>" + formatArea(l.area_m2) + "</td>" +
        "<td>" + formatPrice(l.price, l.price_unknown) + "</td>" +
        "<td>" + formatPrice(l.price_per_m2, l.price_unknown) + "</td>" +
        "<td>" + formatDate(l.removed_date) + "</td>" +
        "<td><a class='portal-link' href='" + escHtml(l.url) + "' target='_blank' rel='noopener'>" +
          escHtml(l.portal) + "</a></td>" +
        "</tr>";
    }});
    body.innerHTML = html;

    // If status filter is "removed", expand the section
    if (forceShow) {{
      document.getElementById("removed-content").classList.add("open");
      document.getElementById("removed-arrow").classList.add("open");
    }}
  }}

  // --- Toggle removed section ---
  document.getElementById("removed-toggle").addEventListener("click", function() {{
    var content = document.getElementById("removed-content");
    var arrow = document.getElementById("removed-arrow");
    content.classList.toggle("open");
    arrow.classList.toggle("open");
  }});

  // --- Event listeners ---
  var filterIds = ["filter-status", "filter-type", "filter-location",
    "filter-price-min", "filter-price-max", "filter-area-min", "filter-area-max", "filter-sort"];
  filterIds.forEach(function(id) {{
    var el = document.getElementById(id);
    if (el) el.addEventListener("change", filterAndSort);
    if (el && (el.type === "number")) el.addEventListener("input", filterAndSort);
  }});

  // --- Init ---
  populateLocations();
  loadFilters();
  updateStats();
  filterAndSort();
}})();
</script>
</body>
</html>"""
