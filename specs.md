# Reality Fetcher v2 — Complete Specification

## 1. Project Overview

Automated Czech real estate monitoring system that scrapes 18 portals, filters/deduplicates listings, and serves results via GitHub Pages with email notifications.

**Architecture**: GitHub Actions (cron) → Python scrapers → JSON data files → Static HTML dashboard → Gmail SMTP notifications

**No database at runtime.** JSON files in the repo are the data store. Git history tracks all changes.

---

## 2. Monitoring Areas

### FM (Frydek-Mistek) — Primary
- **Types**: `dum` (house), `pozemek` (land)
- **Max price**: 10,000,000 CZK
- **Min area**: 750 m²
- **Email**: `dav.plev@seznam.cz`
- **Page**: `fm.html`

### Poruba (Ostrava-Poruba) — Secondary
- **Types**: `byt` (apartment)
- **Max price**: 4,000,000 CZK
- **Min area**: 20 m²
- **Email**: `ivos.pleva@gmail.com`
- **Page**: `poruba.html`

---

## 3. Dashboard Design

### Per-area page (fm.html, poruba.html)

**Header bar:**
- Area name + last updated timestamp
- Summary stats: total active | new today | price changes | removed

**Sticky filter bar** (state persisted in localStorage):
- **Status**: All / New / Price changed / Removed
- **Type**: House / Land (FM only; hidden on Poruba)
- **Location**: dropdown of village/city names (populated from data)
- **Price range**: min-max number inputs
- **Area range**: min-max number inputs
- **Sort by**: Date added (default, newest first) / Price asc/desc / Price per m² asc/desc / Area asc/desc

**Listing rows** (table or card layout):
| Column | Description |
|--------|-------------|
| Type | Badge: `dum` / `pozemek` / `byt` |
| Location | Village name — clickable Google Maps link if coordinates available |
| Area | Land area in m² |
| Price | Current price in CZK, formatted with thousands separator |
| Price/m² | Calculated, formatted |
| Price change | Yellow highlight background. Arrow ↑/↓ with % change. Shows `old → new` |
| Date added | Date first seen by monitor |
| Link | Button/link to original portal listing |
| NEW badge | Green badge for listings added in the latest run |

**Price change styling:**
- Yellow background on the entire row
- `↓ -12.5%` (green text for drops = good for buyer)
- `↑ +5.0%` (red text for rises)

**Removed listings section:**
- Collapsed by default at bottom of page
- Strikethrough styling on title/price
- Shows removal date
- Separate from active listings, not mixed in

### No frameworks. Single HTML file per area with inline CSS + vanilla JS. JSON data embedded or loaded from separate file.

---

## 4. Email Notifications

**Provider**: Gmail SMTP (`smtp.gmail.com:587`, TLS, App Password)

**Trigger**: Only sent when changes exist (new listings, price changes, or removals)

**Separate emails per area** with different recipients.

**Email content** (HTML):
```
Subject: [Reality Monitor] FM: 3 nové, 1 změna ceny, 2 smazané

Nové inzeráty (3):
• Stavební pozemek 2,473 m² — Frýdlant n.O. — 7,980,000 Kč (3,227 Kč/m²) [odkaz]
• ...

Změny cen (1):
• Rodinný dům 180 m² — Baška — 8,990,000 → 7,500,000 Kč (↓ -16.6%) [odkaz]

Smazané (2):
• Pozemek 800 m² — FM-Lískovec — byl 3,840,000 Kč
• ...
```

---

## 5. Data Model

### JSON structure per area (`data/fm.json`, `data/poruba.json`)

```json
{
  "generated": "2026-04-02T07:00:00+02:00",
  "area": {
    "name": "Frýdek-Místek",
    "slug": "fm",
    "types": ["dum", "pozemek"],
    "max_price": 10000000,
    "min_area": 750
  },
  "listings": [
    {
      "id": "sreality_12345",
      "status": "active",
      "type": "pozemek",
      "title": "Stavební pozemek 2,473 m²",
      "location": "Frýdlant nad Ostravicí",
      "coordinates": [49.527, 18.359],
      "area_m2": 2473,
      "price": 7980000,
      "price_per_m2": 3227,
      "price_unknown": false,
      "area_unknown": false,
      "url": "https://www.sreality.cz/detail/...",
      "portal": "sreality",
      "added": "2026-03-28",
      "updated": "2026-04-01",
      "price_history": [
        {"date": "2026-03-28", "price": 8990000},
        {"date": "2026-04-01", "price": 7980000}
      ],
      "removed_date": null
    }
  ]
}
```

**Status values**: `active`, `removed`

**On each run:**
1. Load previous JSON
2. Scrape all portals
3. For each new normalized listing:
   - If not in previous data → `status: "active"`, `added: today`
   - If in previous data and price changed → append to `price_history`, `updated: today`
   - If in previous data and unchanged → keep as-is
4. For listings in previous data but not in current scrape → `status: "removed"`, `removed_date: today`
5. Save updated JSON
6. Generate HTML from JSON
7. Send email with diff (new + changed + removed)

---

## 6. Scraping Pipeline

### 6.1 Scraper Registry

All 18 portals with their search configurations. Each scraper is a Python module implementing the same interface.

```python
class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self, listing_type: str) -> list[RawListing]:
        """Scrape portal for given type (dum/pozemek/byt)."""
        pass
```

### 6.2 Portal Configurations

#### 1. Sreality (priority 1)
- **API**: `https://www.sreality.cz/api/cs/v2/estates` (REST JSON)
- **Pagination**: 60/page, max 100 pages
- **Search params**:
  - dum: `category_main_cb=2, category_type_cb=1, region=moravskoslezsky-kraj`
  - pozemek: `category_main_cb=3, category_sub_cb=19, category_type_cb=1, region=moravskoslezsky-kraj, district=frydek-mistek`
  - byt: `category_main_cb=1, category_type_cb=1, region=moravskoslezsky-kraj, district=ostrava-mesto`
- **GPS**: `gps.lat`, `gps.lon` fields
- **Portal ID**: `hash_id`

#### 2. iDNES Reality (priority 2)
- **URL**: `https://reality.idnes.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 25/page, `page` param
- **Search params**:
  - dum: `/s/prodej/domy/rodinne/cena-do-10000000/okres-frydek-mistek/` + `s-qc[groundAreaMin]=750`
  - pozemek: `/s/prodej/pozemky/stavebni-pozemek/cena-do-10000000/okres-frydek-mistek/` + `s-qc[groundAreaMin]=750`
  - byt: `/s/prodej/byty/okres-frydek-mistek/`
- **Selectors**: `div.c-products__inner`, `h2.c-products__title`, `p.c-products__price`

#### 3. RealityMix (priority 3)
- **URL**: `https://realitymix.cz/vypis-nabidek/`
- **Parsing**: HTML selectolax
- **Pagination**: 20/page, `stranka` param
- **Search params** (GET form):
  - All: `form[inzerat_typ]=1, form[adresa_kraj_id][]=132, form[adresa_region_id][132][]=3802, form[cena_normalizovana__to]=10000000`
  - dum: `form[nemovitost_typ][]=6, form[plocha__from]=750`
  - pozemek: `form[nemovitost_typ][]=3, form[plocha__from]=750`
  - byt: `form[nemovitost_typ][]=2`

#### 4. Bezrealitky (priority 4)
- **URL**: `https://www.bezrealitky.cz`
- **Parsing**: Next.js `__NEXT_DATA__` JSON extraction
- **Pagination**: 15/page, `page` param
- **Search params**:
  - dum: `/vypis/nabidka-prodej/dum/moravskoslezsky-kraj` + `priceTo=10000000`
  - pozemek: `/vypis/nabidka-prodej/pozemek/moravskoslezsky-kraj` + `priceTo=10000000, surfaceLandFrom=750, landType=STAVEBNI`
  - byt: `/vypis/nabidka-prodej/byt/moravskoslezsky-kraj` + `priceTo=10000000`
- **Note**: Apollo cache with `__ref` resolution for images

#### 5. Bazos (priority 5)
- **URL**: `https://reality.bazos.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 20/page, offset-based (`/prodam/dum/20/`, `/prodam/dum/40/`)
- **Search params**: `hlokalita=73801, humkreis=25, cenado=10000000`
- **Paths**: `/prodam/dum/`, `/prodam/pozemek/`, `/prodam/byt/`
- **Selectors**: `div.inzeraty.inzeratyflex`, `h2.nadpis a`, `div.inzeratycena b span`

#### 6. Realingo (priority 6)
- **URL**: `https://www.realingo.cz`
- **Parsing**: Next.js `__NEXT_DATA__` JSON
- **Pagination**: 40/page, `{N}_strana/` suffix
- **Paths**: `/prodej_domy/Okres_Fr%C3%BDdek-M%C3%ADstek/`, `/prodej_pozemky/...`, `/prodej_byty/...`
- **Data path**: `props.pageProps.store.offer.list.data`

#### 7. Eurobydleni (priority 7)
- **URL**: `https://www.eurobydleni.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 12/page, `page-{n}/` suffix
- **Paths**: `/domy/frydek-mistek/prodej/`, `/pozemky/...`, `/byty/...`
- **Price**: `meta[itemprop='price']` or text fallback

#### 8. Sousede (priority 8)
- **URL**: `https://reality.sousede.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 20/page, `strana` param
- **Paths**: `/prodej/rodinne-domy/moravskoslezsky-kraj/frydek-mistek/`, etc.
- **Selectors**: `div.i-estate`, `div.title h3 a`, `div.price div.value`

#### 9. RE/MAX (priority 9)
- **URL**: `https://www.remax-czech.cz`
- **Parsing**: HTML selectolax (data attributes)
- **Pagination**: 21/page, `stranka` param
- **Paths**: `/reality/domy-a-vily/prodej/moravskoslezsky-kraj/`, etc.
- **Data attributes**: `data-title`, `data-price`, `data-gps` (DMS format: `49°36'58.7"N,18°19'56.4"E`)
- **Note**: GPS in DMS format requires degree/minute/second conversion

#### 10. Reality.cz (priority 10)
- **URL**: `https://www.reality.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 25/page, complex `g` param: `g={page-1}-0-{total}`
- **Paths**: `/prodej/domy/moravskoslezsky-kraj/frydek-mistek/`, etc.
- **GPS**: In CSS class names — `gpsx49.6547 gpsy18.3323`
- **Selectors**: `div.xvypis`, `p.vypisnaz a`, `p.vypiscena span strong`

#### 11. RealCity (priority 11)
- **URL**: `https://www.realcity.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 20/page, `list-page` param + `list-perPage=20`
- **Paths**: `/prodej-domu/frydek-mistek-82`, `/prodej-pozemku/...`, `/prodej-bytu/...`
- **Portal ID**: `data-advertise` attribute

#### 12. RealHit (priority 12)
- **URL**: `https://realhit.cz`
- **Parsing**: JSON-LD from `<script type="application/ld+json">`
- **Pagination**: 20/page, `strana/{n}/` suffix
- **Paths**: `/prodej/domy/frydek-mistek/`, etc.
- **GPS**: `geo.latitude`, `geo.longitude`

#### 13. Century 21 (priority 13)
- **URL**: `https://www.century21.cz`
- **Parsing**: HTML selectolax (server-rendered Next.js)
- **Pagination**: 20/page, `page` param
- **Params**: `typ=prodej&druh=domy&region=moravskoslezsky-kraj`, etc.
- **Portal ID**: UUID from href

#### 14. Moravske Reality (priority 14)
- **URL**: `https://severo.moravskereality.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 20/page, `strana` param + `sff=1`
- **Paths**: `/frydek-mistek/prodej/rodinne-domy/`, etc.
- **Selectors**: `article.i-estate`, `h2.i-estate__header-title a`

#### 15. RK Sting (priority 15)
- **URL**: `https://www.rksting.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 8/page, `p` param
- **Paths**: `/rodinne-domy-moravskoslezsky-kraj/`, etc.
- **Selectors**: `div.result-row`, `h2.heading`, `div.price-col`, `div.size-col`

#### 16. BoReality (priority 16)
- **URL**: `https://www.boreality.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 20/page, `{page}/` suffix
- **Paths**: `/prodej/rodinne-domy/moravskoslezsky/`, etc.
- **Selectors**: `article.estateListItem`

#### 17. Reality Regio (priority 17)
- **URL**: `https://www.realityregio.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 20/page, `page-{n}/` suffix
- **Paths**: `/reality/moravskoslezsky/`, etc.
- **Note**: Must filter `strong.list-items__item__type == "prodej"` at parse time

#### 18. MM Reality (priority 18)
- **URL**: `https://www.mmreality.cz`
- **Parsing**: HTML selectolax
- **Pagination**: 12/page, `page` param
- **Paths**: `/nemovitosti/prodej/domy/moravskoslezsky-kraj/`, etc.
- **Data from**: `button[data-realty-id]` attributes

### 6.3 Rate Limiting
- **All portals**: 1.0–2.5s random delay between page requests
- **429 response**: Respect `Retry-After` header or wait 600s
- **Timeout**: 30s per HTTP request
- **Circuit breaker**: 3 consecutive failures → skip portal for 7 days (tracked in `data/portal_health.json`)

### 6.4 Normalization Pipeline

```
RawListing (portal output)
  → normalize_type(raw_type, url) → "dum" | "pozemek" | "byt"
  → normalize_price(raw_price) → (int | None, is_unknown: bool)
  → normalize_area(raw_area, title) → (int | None, is_unknown: bool)  [FIXED]
  → resolve_location(raw_location, aliases) → (canonical_name, coordinates) | None
  → NormalizedListing
```

#### CRITICAL FIX: Area Parsing

v1 bug: room count concatenated with area ("3+1 65 m²" → 165 m²).

**v2 fix**: Extract area as the **last standalone number before m²/m2**, ignoring room patterns like `N+1`, `N+kk`:
```python
# Strip room patterns first: "3+1", "2+kk", "1+1"
cleaned = re.sub(r'\d\+\d|\d\+kk|\d\+KK', '', raw)
# Then find last m² match
match = re.findall(r'(\d[\d\s,.]*)\s*m[²2]', cleaned)
if match:
    return int(match[-1].replace(' ', '').replace(',', ''))
```

### 6.5 Filters (applied per-area)

1. **TypeFilter** — listing type must be in area's allowed types
2. **URLPatternFilter** — reject if URL contains blocked patterns (see Section 8)
3. **PriceFilter** — reject if price > max_price (price_unknown passes with flag)
4. **AreaFilter** — reject if area < min_area (area_unknown passes with flag)
5. **LocationFilter** — reject if locality not in whitelist (resolved via aliases)
6. **BlacklistFilter** — reject if title/description contains blacklisted word (case-insensitive, diacritics-normalized)

### 6.6 Cross-Portal Deduplication

**Priority order** (higher priority portal becomes the "primary" listing):
1. sreality, 2. idnes, 3. realitymix, 4. bezrealitky, 5. bazos, 6. realingo, 7. eurobydleni, 8. sousede, 9. remaxcz, 10. realitycz, 11. realcity, 12. realhit, 13. century21, 14. moravskereality, 15. rksting, 16. boreality, 17. realityregio, 18. mmreality

**5 matching strategies** (checked in order):

1. **Exact title** — normalize (lowercase, strip diacritics, strip non-alnum, ² → 2), compare
2. **Numeric fingerprint** — extract all meaningful numbers from title, sort, join with `_`. Match if identical.
3. **Price + Area key** — `{price}_{area}` if both price > 100 and area > 0
4. **Price only** — match if price identical and non-round (not exact millions)
5. **Area only** — match if area identical and non-round (not exact hundreds)

**Result**: Keep only the primary (highest priority portal). Secondary listings are discarded. The primary listing's URL is what the user sees.

---

## 7. Locality Configuration

### 7.1 FM Whitelisted Municipalities (29)

| ID | Name | Coordinates |
|----|------|-------------|
| frydek_mistek | Frýdek-Místek | 49.6878, 18.3498 |
| frydlant | Frýdlant nad Ostravicí | 49.59, 18.36 |
| celadna | Čeladná | 49.54, 18.34 |
| ostravice | Ostravice | 49.53, 18.39 |
| baska | Baška | 49.6422, 18.3553 |
| kuncicky_u_basky | Kunčičky u Bašky | 49.635, 18.365 |
| hodonovice | Hodoňovice | 49.65, 18.37 |
| chlebovice | Chlebovice | 49.655, 18.31 |
| fm_liskovec | FM-Lískovec | 49.68, 18.35 |
| fm_skalice | FM-Skalice | 49.70, 18.38 |
| zelinkovice | Zelinkovice | 49.66, 18.30 |
| lysuvky | Lysůvky | 49.65, 18.32 |
| frydlant_lubno | Frýdlant-Lubno | 49.59, 18.36 |
| frydlant_nova_ves | Frýdlant-Nová Ves | 49.58, 18.35 |
| bruzovice | Bruzovice | 49.695, 18.39 |
| dobra | Dobrá | 49.67, 18.41 |
| janovice | Janovice | 49.61, 18.39 |
| malenovice | Malenovice | 49.61, 18.44 |
| metylovice | Metylovice | 49.60, 18.34 |
| palkovice | Palkovice | 49.635, 18.32 |
| paskov | Paskov | 49.73, 18.29 |
| przno | Pržno | 49.6264, 18.3756 |
| pstruzi | Pstruží | 49.58, 18.38 |
| raskovice | Raškovice | 49.61, 18.47 |
| repiste | Řepiště | 49.72, 18.31 |
| sedliste | Sedliště | 49.7097, 18.37 |
| staric | Staříč | 49.67, 18.31 |
| sviadnov | Sviadnov | 49.71, 18.32 |
| zaben | Žabeň | 49.72, 18.33 |

### 7.2 Poruba Whitelisted Municipalities (1)

| ID | Name | Coordinates |
|----|------|-------------|
| poruba | Ostrava-Poruba | 49.8361, 18.1694 |

### 7.3 Locality Aliases

Aliases map portal-specific name variants to canonical locality IDs. Stored in `config/aliases.json`.

**FM aliases** (examples):
- "Baška", "Baska u Frydku-Mistku" → `baska`
- "Baška - Kunčičky u Bašky", "Kunčičky u Bašky" → `kuncicky_u_basky`
- "Frydek-Mistek - Chlebovice", "Frydek-Mistek, cast Chlebovice" → `chlebovice`
- "FM-Lískovec", "Frýdek-Místek - Lískovec", "Lískovec" → `fm_liskovec`

**Poruba aliases**:
- "Ostrava-Poruba", "Ostrava - Poruba", "Poruba", "Ostrava, Poruba" → `poruba`
- "Ostrava708 00", "Ostrava 708 00" → `poruba` (Bazos postal code format)

Full alias list migrated from v1 seed.surql (45+ entries).

---

## 8. Blacklist & URL Patterns

### 8.1 FM Blacklist Words (100+ entries)

**Unwanted property types**: les, lesni, zemedelsky, zemedelska, zemědělská, orna puda, pole, louka, louky, chata, chalupa, rekreacni, zahrada, zahradkarska kolonie, komercni, komerční, komercni vystavba, komerční výstavba, komerční pozemek, prumyslovy, garaz, pasport, provozni, provozní, mobilni dum, mobilní dům, vinice, byt, bytu, ordinace, kancelar, kancelář

**Transaction types**: pronajem, pronájem, rezervovano, rezervováno

**Blocked municipalities** (in FM district but outside search area): bila, bílá, bukovec, bystrice, bystřice, dobratice, domaslavice, dolni domaslavice, dolní domaslavice, horni domaslavice, horní domaslavice, frycovice, fryčovice, hnojnik, hnojník, hradek, hrádek, hukvaldy, jablunkov, komorni lhotka, komorní lhotka, krasna, krásná, krmelín, lucina, lučina, milikov, milíkov, moravka, morávka, mosty u jablunkova, mosty u jabl, navsi, návší, nosovice, nydek, nýdek, pazderna, pazderná, pisek, písek, prazmo, reka, řeka, ropice, sobesovice, soběšovice, stare hamry, staré hamry, stritez, střítež, tranovice, třanovice, trinec, třinec, trojanovice, vendryne, vendryně, vojkovice, vysni lhoty, vyšní lhoty, lomna, lomná, horni tosanovice, horní tošanovice

### 8.2 Poruba Blacklist Words (57 entries)

**Rentals**: pronájem, pronajem, podnájem, podnajem
**Reserved/sold**: rezervováno, rezervovano, prodáno, prodano
**Commercial**: komercni, komerční, kancelář, kancelar, ordinace, provozní, provozni
**Garage/parking**: garáž, garaz, garážové stání, garazove stani, parking
**Storage**: sklep, skladový, skladovy
**Auctions**: dražba, drazba, aukce
**Wanted/requests**: poptávka, poptavka, hledám, hledam, koupím, koupim, sháním, shanim
**Shares/exchanges**: spoluvlastnický podíl, spoluvlastnicky podil, podíl na bytové, podil na bytove, 1/2 podíl, 1/3 podíl, 1/4 podíl, 1/8 podíl, výměna bytu, vymena bytu, výměnou, vymenou, vyměním, vymenim, nabídněte, nabidnete

### 8.3 FM URL Patterns (blocked substrings in listing URL)

```
vodni-ploch, rybnik, louka, les, zahrady, zemedelsk, orna-puda,
ostatni-ostatni, ostatni-pozemky, prumyslovy, areal, komercni,
apartma, na-klic, rekreacni, ostrava-hrabova, kuncice-pod-ondrej,
oldrichovic, brusperk, trinec
```

### 8.4 Blacklist Matching Algorithm

```python
def matches_blacklist(text: str, blacklist: list[str]) -> bool:
    normalized = strip_diacritics(text.lower())
    for word in blacklist:
        norm_word = strip_diacritics(word.lower())
        if norm_word in normalized:
            return True
    return False
```

Applied to: title + description + address (concatenated).

---

## 9. GitHub Actions Workflow

### 9.1 Schedule

```yaml
on:
  schedule:
    - cron: '0 5 * * *'   # 07:00 CET (UTC+2)
    - cron: '0 16 * * *'  # 18:00 CET (UTC+2)
  workflow_dispatch:        # Manual trigger
```

### 9.2 Workflow Steps

```yaml
jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: python -m src.main
        env:
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
      - name: Commit data changes
        run: |
          git config user.name "Reality Bot"
          git config user.email "bot@reality-fetcher"
          git add data/ site/
          git diff --cached --quiet || git commit -m "Update $(date +%Y-%m-%d_%H:%M)"
          git push
```

### 9.3 GitHub Secrets

| Secret | Value |
|--------|-------|
| `GMAIL_USER` | Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password (16 chars, from Google Account → Security → App Passwords) |

### 9.4 GitHub Pages

Deploy from `site/` directory on `main` branch. Pages settings: Source = "Deploy from a branch", Branch = `main`, Folder = `/site`.

---

## 10. Project File Structure

```
reality-fetcher-v2/
├── .github/
│   └── workflows/
│       └── scrape.yml              # Cron schedule + manual trigger
├── config/
│   ├── areas.json                  # Area definitions (FM, Poruba) with filters
│   ├── localities.json             # Whitelisted municipalities with coordinates
│   ├── aliases.json                # Portal-specific name → canonical locality mapping
│   ├── blacklist.json              # Blocked words per area
│   └── url_patterns.json           # Blocked URL substrings per area
├── data/
│   ├── fm.json                     # Current FM listings (the "database")
│   ├── poruba.json                 # Current Poruba listings
│   └── portal_health.json          # Circuit breaker state per portal
├── site/
│   ├── index.html                  # Landing page with links to FM / Poruba
│   ├── fm.html                     # FM dashboard (generated)
│   └── poruba.html                 # Poruba dashboard (generated)
├── src/
│   ├── __init__.py
│   ├── main.py                     # Orchestrator: scrape → diff → email → generate
│   ├── models.py                   # RawListing, NormalizedListing dataclasses
│   ├── config.py                   # Load JSON configs
│   ├── scrapers/
│   │   ├── __init__.py             # Registry: SCRAPERS dict mapping name → class
│   │   ├── base.py                 # BaseScraper ABC + shared HTTP client
│   │   ├── sreality.py
│   │   ├── idnes.py
│   │   ├── realitymix.py
│   │   ├── bezrealitky.py
│   │   ├── bazos.py
│   │   ├── realingo.py
│   │   ├── eurobydleni.py
│   │   ├── sousede.py
│   │   ├── remaxcz.py
│   │   ├── realitycz.py
│   │   ├── realcity.py
│   │   ├── realhit.py
│   │   ├── century21.py
│   │   ├── moravskereality.py
│   │   ├── rksting.py
│   │   ├── boreality.py
│   │   ├── realityregio.py
│   │   └── mmreality.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── normalizer.py           # Raw → Normalized (type, price, area, location)
│   │   ├── filters.py              # Filter pipeline (type, URL, price, area, location, blacklist)
│   │   └── dedup.py                # Cross-portal dedup (5 strategies)
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── email_sender.py         # Gmail SMTP sender + HTML email template
│   └── site_generator.py           # Generate static HTML dashboard from JSON data
├── tests/
│   ├── test_normalizer.py          # Area parsing fix verification
│   ├── test_filters.py             # Filter pipeline tests
│   ├── test_dedup.py               # Cross-portal dedup tests
│   └── test_diff.py                # Listing diff logic tests
├── requirements.txt                # httpx, selectolax
└── specs.md                        # This file
```

---

## 11. File Specifications

### 11.1 `config/areas.json`
```json
[
  {
    "slug": "fm",
    "name": "Frýdek-Místek",
    "types": ["dum", "pozemek"],
    "max_price": 10000000,
    "min_area": 750,
    "email_recipients": ["dav.plev@seznam.cz"]
  },
  {
    "slug": "poruba",
    "name": "Ostrava-Poruba",
    "types": ["byt"],
    "max_price": 4000000,
    "min_area": 20,
    "email_recipients": ["ivos.pleva@gmail.com"]
  }
]
```

### 11.2 `config/localities.json`
```json
{
  "fm": [
    {"id": "frydek_mistek", "name": "Frýdek-Místek", "coordinates": [49.6878, 18.3498]},
    {"id": "frydlant", "name": "Frýdlant nad Ostravicí", "coordinates": [49.59, 18.36]},
    {"id": "celadna", "name": "Čeladná", "coordinates": [49.54, 18.34]},
    {"id": "ostravice", "name": "Ostravice", "coordinates": [49.53, 18.39]},
    {"id": "baska", "name": "Baška", "coordinates": [49.6422, 18.3553]},
    {"id": "kuncicky_u_basky", "name": "Kunčičky u Bašky", "coordinates": [49.635, 18.365]},
    {"id": "hodonovice", "name": "Hodoňovice", "coordinates": [49.65, 18.37]},
    {"id": "chlebovice", "name": "Chlebovice", "coordinates": [49.655, 18.31]},
    {"id": "fm_liskovec", "name": "FM-Lískovec", "coordinates": [49.68, 18.35]},
    {"id": "fm_skalice", "name": "FM-Skalice", "coordinates": [49.70, 18.38]},
    {"id": "zelinkovice", "name": "Zelinkovice", "coordinates": [49.66, 18.30]},
    {"id": "lysuvky", "name": "Lysůvky", "coordinates": [49.65, 18.32]},
    {"id": "frydlant_lubno", "name": "Frýdlant-Lubno", "coordinates": [49.59, 18.36]},
    {"id": "frydlant_nova_ves", "name": "Frýdlant-Nová Ves", "coordinates": [49.58, 18.35]},
    {"id": "bruzovice", "name": "Bruzovice", "coordinates": [49.695, 18.39]},
    {"id": "dobra", "name": "Dobrá", "coordinates": [49.67, 18.41]},
    {"id": "janovice", "name": "Janovice", "coordinates": [49.61, 18.39]},
    {"id": "malenovice", "name": "Malenovice", "coordinates": [49.61, 18.44]},
    {"id": "metylovice", "name": "Metylovice", "coordinates": [49.60, 18.34]},
    {"id": "palkovice", "name": "Palkovice", "coordinates": [49.635, 18.32]},
    {"id": "paskov", "name": "Paskov", "coordinates": [49.73, 18.29]},
    {"id": "przno", "name": "Pržno", "coordinates": [49.6264, 18.3756]},
    {"id": "pstruzi", "name": "Pstruží", "coordinates": [49.58, 18.38]},
    {"id": "raskovice", "name": "Raškovice", "coordinates": [49.61, 18.47]},
    {"id": "repiste", "name": "Řepiště", "coordinates": [49.72, 18.31]},
    {"id": "sedliste", "name": "Sedliště", "coordinates": [49.7097, 18.37]},
    {"id": "staric", "name": "Staříč", "coordinates": [49.67, 18.31]},
    {"id": "sviadnov", "name": "Sviadnov", "coordinates": [49.71, 18.32]},
    {"id": "zaben", "name": "Žabeň", "coordinates": [49.72, 18.33]}
  ],
  "poruba": [
    {"id": "poruba", "name": "Ostrava-Poruba", "coordinates": [49.8361, 18.1694]}
  ]
}
```

### 11.3 `config/aliases.json`
```json
{
  "Baška": "baska",
  "Baska u Frydku-Mistku": "baska",
  "Baška - Kunčičky u Bašky": "kuncicky_u_basky",
  "Kunčičky u Bašky": "kuncicky_u_basky",
  "Baška - Hodoňovice": "hodonovice",
  "Baška Hodoňovice": "hodonovice",
  "Hodoňovice": "hodonovice",
  "Baška Kunčičky u Bašky": "kuncicky_u_basky",
  "Frydek-Mistek - Chlebovice": "chlebovice",
  "Frydek-Mistek, cast Chlebovice": "chlebovice",
  "Frydek-Mistek-Chlebovice": "chlebovice",
  "Frýdek-Místek - Chlebovice, okres Frýdek-Místek": "chlebovice",
  "FM-Lískovec": "fm_liskovec",
  "Frýdek-Místek - Lískovec": "fm_liskovec",
  "Lískovec": "fm_liskovec",
  "FM-Skalice": "fm_skalice",
  "Frýdek-Místek - Skalice": "fm_skalice",
  "Skalice": "fm_skalice",
  "Frýdek-Místek - Skalice, okres Frýdek-Místek": "frydek_mistek",
  "Frýdek-Místek - Místek": "frydek_mistek",
  "Zelinkovice": "zelinkovice",
  "Frýdek-Místek - Zelinkovice": "zelinkovice",
  "Lysůvky": "lysuvky",
  "Frýdek-Místek - Lysůvky": "lysuvky",
  "Frýdlant nad Ostravicí - Lubno": "frydlant_lubno",
  "Frýdlant nad Ostravicí - Lubno, okres Frýdek-Místek": "frydlant",
  "Lubno": "frydlant_lubno",
  "Frýdlant nad Ostravicí - Nová Ves": "frydlant_nova_ves",
  "Frýdlant nad Ostravicí - Frýdlant, okres Frýdek-Místek": "frydlant",
  "Dobrá": "dobra",
  "Dobrá u Frýdku-Místku": "dobra",
  "Bruzovice": "bruzovice",
  "Malenovice": "malenovice",
  "Metylovice": "metylovice",
  "Paskov": "paskov",
  "Pstruží": "pstruzi",
  "Řepiště": "repiste",
  "Sviadnov": "sviadnov",
  "Ostrava-Poruba": "poruba",
  "Ostrava - Poruba": "poruba",
  "Ostrava, Poruba": "poruba",
  "Poruba": "poruba",
  "Ostrava - Poruba, okres Ostrava-město": "poruba",
  "Ostrava - Poruba, Ostrava-město": "poruba",
  "Ostrava-Poruba, okres Ostrava-mesto": "poruba",
  "Poruba, Ostrava": "poruba",
  "Ostrava, Ostrava - Poruba": "poruba",
  "Ostrava708 00": "poruba",
  "Ostrava 708 00": "poruba"
}
```

### 11.4 `config/blacklist.json`

Full lists as specified in Section 8.1 and 8.2. Both diacritics and non-diacritics variants included.

### 11.5 `config/url_patterns.json`
```json
{
  "fm": [
    "vodni-ploch", "rybnik", "louka", "les", "zahrady", "zemedelsk",
    "orna-puda", "ostatni-ostatni", "ostatni-pozemky", "prumyslovy",
    "areal", "komercni", "apartma", "na-klic", "rekreacni",
    "ostrava-hrabova", "kuncice-pod-ondrej", "oldrichovic", "brusperk", "trinec"
  ],
  "poruba": []
}
```

### 11.6 `data/portal_health.json`
```json
{
  "sreality": {"active": true, "failures": 0, "deactivated_until": null},
  "idnes": {"active": true, "failures": 0, "deactivated_until": null},
  "realitymix": {"active": true, "failures": 0, "deactivated_until": null},
  "bezrealitky": {"active": true, "failures": 0, "deactivated_until": null},
  "bazos": {"active": true, "failures": 0, "deactivated_until": null},
  "realingo": {"active": true, "failures": 0, "deactivated_until": null},
  "eurobydleni": {"active": true, "failures": 0, "deactivated_until": null},
  "sousede": {"active": true, "failures": 0, "deactivated_until": null},
  "remaxcz": {"active": true, "failures": 0, "deactivated_until": null},
  "realitycz": {"active": true, "failures": 0, "deactivated_until": null},
  "realcity": {"active": true, "failures": 0, "deactivated_until": null},
  "realhit": {"active": true, "failures": 0, "deactivated_until": null},
  "century21": {"active": true, "failures": 0, "deactivated_until": null},
  "moravskereality": {"active": true, "failures": 0, "deactivated_until": null},
  "rksting": {"active": true, "failures": 0, "deactivated_until": null},
  "boreality": {"active": true, "failures": 0, "deactivated_until": null},
  "realityregio": {"active": true, "failures": 0, "deactivated_until": null},
  "mmreality": {"active": true, "failures": 0, "deactivated_until": null}
}
```

### 11.7 `requirements.txt`
```
httpx>=0.27
selectolax>=0.3
```

Only 2 runtime dependencies. Python stdlib handles: `json`, `smtplib`, `email`, `asyncio`, `re`, `dataclasses`, `unicodedata`, `pathlib`, `datetime`.

### 11.8 `src/models.py`
```python
from dataclasses import dataclass, field

@dataclass
class RawListing:
    portal: str
    portal_id: str
    title: str
    url: str
    type_raw: str | None = None
    price_raw: str | None = None
    area_raw: str | None = None
    location_raw: str | None = None
    address_raw: str | None = None
    description: str | None = None
    coordinates: tuple[float, float] | None = None
    images: list[str] = field(default_factory=list)

@dataclass
class NormalizedListing:
    portal: str
    portal_id: str
    title: str
    url: str
    type: str                          # "dum" | "pozemek" | "byt"
    price: int | None
    price_unknown: bool
    area_m2: int | None
    area_unknown: bool
    price_per_m2: int | None           # Calculated: price / area_m2
    location: str                      # Canonical locality name
    location_id: str                   # Locality ID for filtering
    coordinates: tuple[float, float] | None
```

### 11.9 `src/main.py` — Orchestrator Pseudocode

```python
def main():
    # 1. Load configs
    areas = load_areas()
    localities = load_localities()
    aliases = load_aliases()
    blacklists = load_blacklists()
    url_patterns = load_url_patterns()
    portal_health = load_portal_health()

    # 2. Compute union of needed types across all areas
    all_types = set()
    for area in areas:
        all_types.update(area["types"])

    # 3. Scrape all portals
    all_raw = {}  # {portal_name: [RawListing, ...]}
    for portal_name, scraper_cls in SCRAPERS.items():
        if not is_portal_active(portal_health, portal_name):
            continue
        try:
            scraper = scraper_cls()
            for typ in all_types:
                raw = asyncio.run(scraper.scrape(typ))
                all_raw.setdefault(portal_name, []).extend(raw)
            reset_failures(portal_health, portal_name)
        except Exception:
            record_failure(portal_health, portal_name)

    # 4. Process per area
    for area in areas:
        prev_data = load_area_data(area["slug"])
        area_localities = localities[area["slug"]]
        area_blacklist = blacklists[area["slug"]]
        area_url_pats = url_patterns[area["slug"]]
        locality_ids = {loc["id"] for loc in area_localities}

        # Normalize + filter
        candidates = []
        for portal_name, raw_listings in all_raw.items():
            for raw in raw_listings:
                normalized = normalize(raw, aliases)
                if normalized is None:
                    continue
                if not passes_filters(normalized, area, locality_ids,
                                      area_blacklist, area_url_pats):
                    continue
                candidates.append(normalized)

        # Cross-portal dedup
        unique = deduplicate(candidates)

        # Diff against previous data
        new, changed, removed, unchanged = diff_listings(prev_data, unique)

        # Update data file
        updated = build_updated_data(area, unique, removed, prev_data)
        save_area_data(area["slug"], updated)

        # Generate HTML
        generate_html(area, updated)

        # Send email if changes
        if new or changed or removed:
            send_email(area, new, changed, removed)

    # 5. Save portal health
    save_portal_health(portal_health)
```

---

## 12. Migration from v1

### Copy directly:
- Scraper search parameters (all 18 portals) — exact URLs, selectors, pagination
- Locality whitelist + aliases (seed.surql → JSON)
- Blacklist words (seed.surql → JSON)
- URL patterns (main.py → JSON)
- Dedup strategies (cross_dedup.py)
- Portal priority ordering

### Rewrite:
- Remove SurrealDB → JSON file read/write
- Fix area parsing bug (room count concatenation)
- Fix blacklist matching across all portals (rksting rental leak)
- Move all hardcoded config to JSON files
- Replace APScheduler → GitHub Actions cron
- Replace aiohttp health endpoint → GitHub Pages
- Replace Jinja2 templates → inline HTML generation

### New:
- JSON-based data persistence (git-tracked)
- Static HTML dashboard with client-side filtering
- Price change visualization (yellow highlight, ↑↓ arrows, % change)
- Google Maps links for coordinates
- localStorage filter persistence
- Gmail SMTP notifications
- GitHub Actions scheduling
- GitHub Pages hosting

---

## 13. Known v1 Bugs to Fix

1. **Area parsing**: Room count concatenation ("3+1 65 m²" → 165). Fix: strip room patterns before extracting area.
2. **rksting rentals**: "Pronájem" in title not caught by blacklist. Fix: ensure blacklist check runs on normalized title for all portals.
3. **Type misclassification**: ReMax labels land as "Dům". Fix: validate type against URL patterns (e.g., `/pozemky/` in URL → pozemek regardless of portal label).
4. **Price unknown bypass**: Listings with "Na vyžádání" pass all price filters silently. Fix: flag clearly in dashboard, show "Cena na vyžádání" instead of blank.
5. **Manual cleanup burden**: Too many listings require manual removal. Fix: tighter URL pattern filters, validate type from URL, broader blacklist.
