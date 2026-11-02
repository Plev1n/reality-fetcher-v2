# Podobné domy + dossier pro oblíbené – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automaticky hledat domy podobné dvěma vzorovým inzerátům (Pržno, Kunčičky u Bašky), ukazovat je na webu a v e-mailu a k oblíbeným lokálně generovat podrobný MD dossier (parametry, historie inzerce, katastr, rejstříky, kanalizace, trh).

**Architecture:** Část A běží v CI s existujícím scrapem: z aktivních domů oblasti `fm` vezme kandidáty v cenovém rozpětí, stáhne a vyparsuje jejich detailní stránky (cache v `data/details_cache.json`), oboduje je proti profilu v `config/profiles.json`, uloží `data/podobne.json`, vygeneruje `site/podobne.html` a pošle e-mail s novými shodami. Část B je lokální CLI `python -m src.dossier`. Oblíbené drží v `private/favorites.json` (gitignored) a reporty zapisuje mimo veřejný repozitář.

**Tech Stack:** Python 3.12+, httpx, selectolax (lexbor backend), pytest. Externí: ČÚZK INSPIRE WFS, ARES REST, ISIR (HTML lustrace), TED API v3.

**Spec:** Tato konverzace (uživatel delegoval návrh: „nějak to vymysli“) a vzorový report `~/Projects/personal/reality-research/domy-przno-kuncicky-2026-11-02.md`, jehož strukturu má dossier reprodukovat.

## Global Constraints
- Repo `Plev1n/reality-fetcher-v2` je **PUBLIC** a `site/` jde na GitHub Pages. **Jména vlastníků, výsledky ARES/ISIR a dossiery se nikdy nesmí dostat do `data/`, `site/` ani do commitu.** `private/` patří do `.gitignore`. Výchozí výstup dossieru je `~/Projects/personal/reality-research/` (přepsatelné env `REALITY_DOSSIER_DIR`).
- Vzorové inzeráty:
  - `https://reality.idnes.cz/detail/prodej/dum/przno/6a0462f2ac3cc251a50f6853/` (5 500 000 Kč, 135 m², pozemek 1 375 m², 5+kk, 1960)
  - `https://reality.idnes.cz/detail/prodej/dum/baska/6ad877b7046357d39609caed/` (5 990 000 Kč, 110 m², pozemek 1 198 m², 4+1, 1968)
- Profil (výchozí hodnoty v `config/profiles.json`, slug `podobne`): typ `dum`; cena 4 500 000–7 000 000 (ideál 5 000 000–6 500 000); užitná plocha 90–170 (ideál 105–140); pozemek ≥ 800 (ideál 1 000–1 600); místnosti 4–5; mimo město Frýdek-Místek je bonus; práh shody **60/100**; příjemce `dav.plev@seznam.cz`.
- Detail se stahuje jen pro kandidáty bez záznamu v cache. Pauza 1–2,5 s mezi requesty (`BaseScraper._delay`). Nejvýš **40 nových detailů za běh**.
- Žádné nové závislosti.

## Review Focus
1. Detail stránky selže (404, timeout, inzerát stažen): kandidát zůstane bez detailu, obodovaný jen z dat výpisu, a běh nespadne. → test v Tasku 3 (`test_fetch_failure_keeps_candidate`).
2. Inzerát nemá užitnou plochu, jen „135 m² s pozemkem 1 375 m²“ v titulku: parser vezme z titulku obě čísla správně. → test v Tasku 2 (`test_title_fallback_two_areas`).
3. Bazoš/Realingo text bez struktury dt/dd: generický regex najde „užitná plocha (m2): 135“ a „plocha parcely (m2): 1375“. → test v Tasku 2.
4. `private/favorites.json` neexistuje nebo je poškozený: CLI vytvoří prázdný, resp. vypíše srozumitelnou chybu a nic nepřepíše. → test v Tasku 5.
5. ARES/ISIR/TED/WFS nedostupné: dossier se vygeneruje se sekcí „nepodařilo se ověřit“ místo pádu. → test v Tasku 6 (`test_report_with_failed_sources`).

---

### Task 1: Oprava CI – migrace selectolax na lexbor

**Files:** Modify všech 14 `src/scrapers/*.py` s `from selectolax.parser import HTMLParser`; `requirements.txt` (`selectolax>=1.0`). Test: `tests/test_scrapers_import.py`.

- [ ] Test `test_all_scrapers_import`: `import_all_scrapers()` proběhne a `len(SCRAPERS) == 18`.
- [ ] Spustit: FAIL s `ImportError: Modest backend is deprecated`.
- [ ] Nahradit import `from selectolax.lexbor import LexborHTMLParser as HTMLParser` (zbytek API se nemění).
- [ ] Test `test_idnes_card_parse`: minimální HTML karty iDNES (`div.c-products__inner` > `h2.c-products__title` „Prodej domu 135 m² s pozemkem 1 375 m²“, `p.c-products__price` „5 500 000 Kč“, `a.c-products__link` href `/detail/prodej/dum/przno/abc/`) → `_parse_card` vrátí `portal_id == "abc"`, `area_raw == "1 375 m2"`.
- [ ] `pytest -q` → vše PASS. Commit `fix: migrate selectolax to lexbor backend (CI broken since 2026-10-03)`.

### Task 2: Parser detailu inzerátu

**Files:** Create `src/similar/__init__.py`, `src/similar/details.py`. Test `tests/test_details.py`.

**Interfaces – Produces:**
```python
@dataclass
class ListingDetails:
    url: str
    fetched: str                 # ISO date
    usable_area: int | None
    plot_area: int | None
    built_area: int | None
    rooms: int | None            # 5+kk → 5, 4+1 → 4
    disposition: str | None      # "5+kk"
    year_built: int | None       # kolaudace / rok výstavby
    condition: str | None        # "před rekonstrukcí"
    construction: str | None     # "cihlová"
    heating: str | None
    sewer: str | None            # "septik / jímka" | "veřejná kanalizace"
    gas: bool | None
    penb: str | None             # "G"
    agency: str | None
    agent: str | None
    ref_number: str | None       # "IDNES-8391"
    description: str | None
    ok: bool                     # False = fetch/parse failed
def parse_details(html: str, url: str) -> ListingDetails
def details_to_dict(d: ListingDetails) -> dict
def details_from_dict(x: dict) -> ListingDetails
```
Postup: z HTML vytvořit (a) slovník `dt→dd` (iDNES `div.b-definition-columns dl`) a (b) prostý text stránky. Každé pole hledat nejdřív v dt/dd (klíče: „Užitná plocha“, „Plocha pozemku“, „Zastavěná plocha“, „Kolaudace“/„Rok výstavby“, „Stav budovy“, „Konstrukce budovy“, „Odpad“, „Topení“, „PENB“, „Číslo zakázky“), pak regexem v textu (`užitná plocha[^\d]{0,15}(\d[\d\s]*)`, `plocha (parcely|pozemku)[^\d]{0,15}(\d[\d\s]*)`, `(\d)\s*\+\s*(kk|1)`, `(kolaudace|rok výstavby|postaven\w*)[^\d]{0,10}(19|20)\d\d`, `plyn`, `kanalizac`/`septik`/`jímk`, `vytápění[:\s]+([^.\n]+)`), nakonec z titulku `(\d[\d\s]*) m² s pozemkem (\d[\d\s]*) m²`. Agenturu brát z iDNES dataLayer `"listing_brand":"…"`.

- [ ] Testy s minimálními fixturami v `tests/fixtures/` (zkrácené, bez fotek a bez kontaktů):
  - `test_idnes_dl_parse`: `usable_area == 135`, `plot_area == 1375`, `built_area == 100`, `year_built == 1960`, `sewer == "septik / jímka"`, `penb == "G"`, `ref_number == "IDNES-8391"`, `rooms == 5`, `disposition == "5+kk"`.
  - `test_bazos_text_parse`: text „užitná plocha (m2): 135 … plocha parcely (m2): 1375 … dispozici 5+kk“ → `135`, `1375`, `5`.
  - `test_title_fallback_two_areas`: jen `<h1>Prodej domu 110 m² s pozemkem 1 198 m²</h1>` → `usable_area == 110`, `plot_area == 1198`.
  - `test_gas_and_sewer_from_text`: „napojen na obecní vodovod, elektřinu, plyn a kanalizaci“ → `gas is True`, `sewer == "veřejná kanalizace"`.
  - `test_roundtrip_dict`.
- [ ] FAIL → implementovat → PASS. Commit `feat(similar): listing detail parser`.

### Task 3: Profil, skóre a běh „podobné“

**Files:** Create `config/profiles.json`, `src/similar/scoring.py`, `src/similar/run.py`. Modify `src/config.py` (`load_profiles()`, `load_details_cache()`, `save_details_cache()`), `src/main.py` (zavolat po zpracování oblastí). Test `tests/test_scoring.py`, `tests/test_similar_run.py`.

**Interfaces – Produces:**
```python
def score_listing(listing: dict, details: ListingDetails | None, profile: dict) -> tuple[int, list[str]]
    # 0–100 + důvody česky, např. ["cena 5,5 mil. ✓", "pozemek 1 375 m² ✓", "užitná 135 m² ✓"]
async def fetch_details(url: str, client: httpx.AsyncClient) -> ListingDetails   # ok=False při chybě
def select_candidates(area_data: dict, profile: dict) -> list[dict]               # status active, typ, cena v rozpětí (nebo cena neznámá)
async def update_similar(area_data: dict, profile: dict, cache: dict, max_fetch: int = 40) -> dict
    # vrací {"generated", "profile", "matches":[{listing…, "score", "reasons", "details"}], "new_ids":[…]}
```
Váhy: cena 25, užitná plocha 25, pozemek 25, počet místností 10, lokalita 15. Plný počet bodů v ideálu, lineární pokles k hraně rozpětí, 0 mimo rozpětí. Chybějící údaj = polovina vah (neznámé ≠ špatné). Lokalita: 15 za obec mimo `frydek_mistek`, 5 za `frydek_mistek`. `new_ids` = shody ≥ prahu, které nebyly v předchozím `data/podobne.json`.

- [ ] `test_reference_przno_scores_high`: listing Pržno (5 500 000, `location_id` `przno`) + details (135/1375/5) → skóre ≥ 90.
- [ ] `test_reference_kuncicky_scores_high`: (5 990 000, `kuncicky_u_basky`, 110/1291/4) → ≥ 85.
- [ ] `test_out_of_range_low`: 9 500 000 Kč, 300 m², pozemek 400 → < 40.
- [ ] `test_missing_details_half_weight`: bez details, cena 5 500 000, obec → 50–75.
- [ ] `test_fetch_failure_keeps_candidate`: `update_similar` s mockovaným fetch, který vyhodí výjimku → kandidát je v `matches` se skóre z výpisu a do cache se zapíše `ok=False` (dnes se už znovu nestahuje).
- [ ] `test_new_ids_only_new`: předchozí výsledek obsahuje id A → `new_ids` obsahuje jen B.
- [ ] Zapojení do `main.py`: po smyčce oblastí pro každý profil načíst `data/{profile.area}.json` → `update_similar` → uložit `data/podobne.json` a cache. Výjimka v této části jen vypíše chybu a nesmí shodit hlavní běh.
- [ ] PASS. Commit `feat(similar): similarity scoring and pipeline`.

### Task 4: Web `site/podobne.html` a e-mail

**Files:** Modify `src/site_generator.py` (`generate_similar_html(result: dict) -> None`), `src/notifications/email_sender.py` (`send_similar_email(recipients, matches_new, dashboard_url)`), `src/main.py`, `site/index.html` (odkaz). Test `tests/test_similar_site.py`.

Stránka: karta pro každou shodu seřazená podle skóre (skóre, cena, užitná/pozemek, dispozice, rok, kanalizace/plyn, portál, odkaz, důvody, štítek „NOVÉ“). Filtr podle min. skóre (výchozí 60). U každé karty tlačítko „⭐ Kopírovat příkaz“, které zkopíruje `python -m src.dossier add <url>`. Veřejně jen data z inzerátu.

- [ ] `test_similar_html_contains_matches`: HTML obsahuje URL shody, „92“ (skóre) a text `python -m src.dossier add`.
- [ ] `test_similar_html_no_private_fields`: vstup s klíčem `owners` → v HTML se neobjeví.
- [ ] E-mail se pošle jen při neprázdném `new_ids`.
- [ ] PASS. Commit `feat(similar): dashboard page and email for new matches`.

### Task 5: Oblíbené – úložiště a CLI

**Files:** Create `src/dossier/__init__.py`, `src/dossier/__main__.py`, `src/dossier/favorites.py`. Modify `.gitignore` (`private/`). Test `tests/test_favorites.py`.

**Interfaces – Produces:**
```python
FAVORITES_PATH = ROOT / "private" / "favorites.json"
def load_favorites(path: Path = FAVORITES_PATH) -> list[dict]   # chybí → []; poškozený JSON → ValueError s cestou
def save_favorites(favs: list[dict], path: Path = FAVORITES_PATH) -> None
def add_favorite(url: str, note: str | None = None, path=...) -> dict   # duplicita URL → vrátí existující
```
Záznam oblíbeného:
```json
{"url": "...", "added": "2026-11-02", "note": null,
 "katastr": {"obec": "Testov", "ku_code": 600001, "ku_name": "Testov", "lv": 1,
             "parcels": ["10", "11/2"],
             "owners": ["Příjmení Jméno"],
             "restrictions": {"10": ["Zákaz zcizení"]},
             "other_entries": [], "price_records": {"11/2": 1}}}
```
`katastr` vyplňuje uživatel ručně z nahlížení do KN (nahlížení blokuje automatické dotazy). CLI vypisuje šablonu.

CLI: `add <url> [--note]`, `list`, `build [--id N | --all] [--out DIR]`, `template` (vypíše prázdný blok `katastr`).

- [ ] `test_load_missing_returns_empty`, `test_load_corrupt_raises_and_keeps_file`, `test_add_dedup`, `test_gitignore_has_private`.
- [ ] PASS. Commit `feat(dossier): favorites storage and CLI`.

### Task 6: Zdroje dossieru a generování MD

**Files:** Create `src/dossier/katastr.py`, `src/dossier/registries.py`, `src/dossier/history.py`, `src/dossier/market.py`, `src/dossier/municipality.py`, `src/dossier/report.py`. Test `tests/test_dossier.py` (síť vždy mockovaná).

**Interfaces – Produces:**
```python
# katastr.py
def parcel_areas(ku_code: int, parcels: list[str], client) -> dict[str, int | None]   # WFS FILTER nationalCadastralReference "{ku}-{parcela}"
def assess_restrictions(restrictions: dict[str, list[str]], other_entries: list[str]) -> list[dict]
    # [{"level": "high"|"medium"|"low", "title": ..., "explain": ...}]; pravidla níže
def plot_check(listing_plot: int | None, built_area: int | None, total: int) -> str
    # "sedí" | "sedí bez zastavěné plochy (total − built)" | "nesedí: …"
# registries.py
def ares_lookup(name: str, client) -> list[dict]     # POST https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/vyhledat {"obchodniJmeno": name}
def isir_lookup(surname: str, first: str, client) -> list[dict]   # GET isir.justice.cz/isir/ueu/vysledek_lustrace.do…; vrací [{"name","city","case","state"}] – bez rodného čísla
# history.py
def listing_history(url: str, details: ListingDetails, repo_root: Path) -> list[dict]
    # shody napříč data/*.json a git historií data/fm.json (vzorek každého 5. commitu + poslední) podle: stejná cena ±0 a (stejný normalizovaný titulek nebo stejná obec), nebo stejné plot_area
# market.py
def market_stats(area_data: dict, location_id: str) -> dict   # medián/min/max/počet pro obec a pro celou oblast; Kč/m² užitné
# municipality.py
def sewer_tenders(municipality: str, client) -> list[dict]    # TED v3 POST /v3/notices/search, query 'FT="<obec>" AND (FT=kanalizace OR FT=ČOV)'
# report.py
def build_report(fav: dict, details: ListingDetails, ctx: dict) -> str   # Markdown
```
Pravidla `assess_restrictions`: „Zákaz zcizení“ → high; „Věcné břemeno“ spolu se zákazem → high (pravděpodobné doživotní bydlení po darování); samotné věcné břemeno → medium (ověřit typ: cesta/sítě vs. bydlení); „Zástavní právo“ → low (hypotéka, úschova); „Exekuce“/„Plomba“/„Insolvence“ v other_entries → high; závazky typu „neumožnit zápis nového zást. práva“ → low (doprovod hypotéky). Parcela s 0 cenovými údaji a high omezeními → poznámka „pravděpodobně nabyto darem/dědictvím“.

Struktura reportu zrcadlí vzor (`reality-research/domy-przno-kuncicky-2026-11-02.md`): Shrnutí (tabulka + riziko), Inzerát, Historie inzerce, Katastr (tabulka parcel, součet, plot_check, omezení s vysvětlením), Vlastník – rejstříky (jen když jsou `owners`), Kanalizace/obec (TED), Trh, Checklist (generovaný z rizik a chybějících dat), Zdroje. Chybějící `katastr` → sekce s návodem (kde v nahlížení do KN co najít a šablona JSON). Výstup: `{out}/{slug-obce}-{portal_id}.md` + `{out}/index.md`.

- [ ] `test_assess_przno`: restrikce Pržna → aspoň jedna `high` s textem obsahujícím „zákaz zcizení“.
- [ ] `test_assess_mortgage_low`: `{"1200": ["Zástavní právo smluvní"]}` → jen `low`.
- [ ] `test_plot_check_minus_built`: listing 1198, built 93, total 1291 → obsahuje „bez zastavěné plochy“.
- [ ] `test_parcel_areas_parses_wfs`: mock XML s `areaValue uom="m2">166` → `{"1203": 166}`.
- [ ] `test_isir_no_birth_number`: mock HTML se smyšleným rodným číslem → výstup ho neobsahuje (všechny osoby v testech jsou smyšlené).
- [ ] `test_report_with_failed_sources`: všechny zdroje vyhodí výjimku → report obsahuje „nepodařilo se ověřit“ a sekce Inzerát.
- [ ] `test_report_without_katastr_has_guide`.
- [ ] PASS. Commit `feat(dossier): sources and markdown report`.

### Task 7: End-to-end ověření

- [ ] `pytest -q` → vše PASS.
- [ ] Lokálně `python -m src.main` s `GMAIL_*` neprázdnými? Ne – spustit bez e-mailu (sender bez credentials jen vypíše „skipping“; ověřit v `email_sender.py`). Ověřit, že vznikne `data/podobne.json` a `site/podobne.html` a že oba vzorové inzeráty (pokud jsou ve výpisu) mají skóre ≥ 85.
- [ ] `agent-browser` screenshot `site/podobne.html`.
- [ ] `python -m src.dossier add` oba vzorové inzeráty + vyplnit `katastr` z konverzace → `build --all` → porovnat s ručním vzorovým reportem (sekce a hlavní závěry se shodují).
- [ ] `git status`: `private/` ani dossier se nenabízí ke commitu. Commit, push, ručně spustit workflow (`gh workflow run scrape.yml`) a ověřit zelený běh.
