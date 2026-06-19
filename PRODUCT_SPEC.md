# PRODUCT SPEC — the analyst-first build spec

Build-ready refinement of `PRODUCT.md`. **Audience locked: trade / sourcing analysts &
seasonal buyers.** Everything below is grounded in the committed columns
(`data/atlas/*.csv`, `data/market/*.csv`) with a data-availability note per chart.

> Emphasis shift for this audience: lead with **the relay, lanes, $/kg, and share-shifts**
> (the data picture). The coverage map stays a first-class page (the moat) but is not the
> front door. Analysts want **density, prices everywhere, YoY deltas, shareable links, and
> CSV export** — not whitespace and big type.

---

## 1. Design tenets (trade-analyst)

1. **$/kg is the unit of trust.** Every flow chart pairs volume with realised unit value.
2. **Always show the delta.** Rank, share, price → show YoY change (▲/▼ + pp/%) next to the level.
3. **Provisional is loud.** Latest ~2 Comtrade years are provisional; render them hatched/greyed and labelled, never as solid fact.
4. **Every number is clickable to its source.** Provenance stamp on every chart (§7).
5. **Shareable + exportable.** Every view encodes state in the URL; every table has "copy CSV".
6. **Dense, fast, static.** Information-rich screens; sub-second; no backend.

---

## 2. Information architecture (re-prioritised)

```
The Global Blueberry Atlas         [commodity: ▼ Blueberry]   [year: ▼ 2023 (final)]
├── 1. THE YEAR        (overview / analyst front door)        ← relay, ranking, prices
├── 2. LANES & PRICES  (the explorer — analysts live here)    ← exporter→importer, $/kg
├── 3. COUNTRY         (profiles, the spine)                  ← per country, data + coverage card
├── 4. THE ATLAS       (coverage map — the moat)              ← registry as a matrix
└── 5. DEEP DIVE       (UK/Chile/Peru editorial — depth proof)
```

Global controls (persist across views, encoded in URL): **commodity**, **reference year**.

---

## 3. Wireframes

### 3.1 THE YEAR (landing)
```
┌───────────────────────────────────────────────────────────────────────────┐
│ THE GLOBAL BLUEBERRY ATLAS                       commodity ▼   year ▼ 2023  │
│ KPI strip:  World exports $5.11B ▲6%  ·  827k t ▲3%  ·  Peru #1 33% ▲1pp   │
│             ·  top importer USA 35%  ·  ~250 lanes  ·  data 2023 (final)    │
├───────────────────────────────────────────────────────────────────────────┤
│ THE RELAY  — who supplies the world each month        [vol ▾ / value]      │
│ ████ stacked-area, x=Jan..Dec, series=top origins; hover=share% + $/kg     │
│ caption: Chile owns Jan–Feb · Spain the spring · US/Canada summer · Peru    │
│          Sep–Nov. Supply-side (export volume).            [source stamp]    │
├──────────────────────────────────────┬────────────────────────────────────┤
│ EXPORTER LADDER  (bar + Δshare)      │ PRODUCTION ≠ EXPORTS               │
│ Peru     ███████████ 33%  ▲1pp $7.8  │ scatter: x=production_t (FAO)       │
│ Neth.    ████ 11% ▼  $8.1 (re-export)│ y=export value; bubble=yield        │
│ Spain    ████ 10% ▲  $7.1            │ labels NL (ships,grows≈0), USA      │
│ Chile    ███ 8%  ▼  $4.7             │ (grows,eats), Peru (grows→ships)   │
│ …                                    │                       [stamp]       │
├──────────────────────────────────────┴────────────────────────────────────┤
│ WORLD MAP  choropleth export value, toggle exporter/importer  [stamp]      │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.2 LANES & PRICES (explorer)
```
┌───────────────────────────────────────────────────────────────────────────┐
│ LANES & PRICES        from ▼ [Peru]   to ▼ [United States]   [↔ swap]      │
├──────────────────────────────────────┬────────────────────────────────────┤
│ LANE OVER TIME (Peru→USA)            │ WHO PAYS WHAT into [USA] (year)     │
│ dual line: $/kg (L) + volume (R),    │ ranked bars of $/kg by origin,      │
│ provisional years hatched            │ volume as bar width        [stamp]  │
│ mirror gap: exp-reported/imp 1.03    ├────────────────────────────────────┤
│                          [stamp]     │ LANE SEASONALITY (monthly $/kg+vol) │
│                                      │ when this lane ships + price arc    │
├──────────────────────────────────────┴────────────────────────────────────┤
│ FREIGHT WEDGE (origins w/ data): FOB vs CIF $/kg + gap   [Chile/Peru only] │
│ TABLE: all Peru lanes — importer · vol · $/kg · share · Δ   [copy CSV]     │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.3 COUNTRY profile (e.g. Peru)
```
┌───────────────────────────────────────────────────────────────────────────┐
│ PERU   [exporter ●]  #1 exporter 33% ▲1pp $7.8/kg  ·  #2 producer 354kt    │
├──────────────────────────────────────┬────────────────────────────────────┤
│ EXPORT DESTINATIONS (bar + $/kg)     │ COVERAGE CARD            [→ Atlas]   │
│ USA ███████ $8.5 · NL ███ $7.8 · …   │ free+wired   6  ▓▓▓▓▓▓             │
│ SEASONALITY (monthly export share)   │ free-unwired 6  ░░░░░░             │
│ PRODUCTION/AREA/YIELD trend (FAO)    │ paid         0                     │
│ FORECAST callout (USDA): prod 355k / │ none         3  ██                 │
│   exp 335k MT CY2025                  │ notable gap: cultivar-per-shipment  │
│ CLIMATE: La Libertad tmin/t2m, frost │ (none); BoL identity (paid)         │
│   line (frost-free, irrigated)       │                          [stamp]    │
├──────────────────────────────────────┴────────────────────────────────────┤
│ PROVENANCE: Comtrade(2023,final,free) · FAOSTAT(free) · USDA-FAS(free) …    │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.4 THE ATLAS (coverage matrix)
```
┌───────────────────────────────────────────────────────────────────────────┐
│ THE ATLAS — what you can know        filters: role ▼  access ▼  [search]   │
│ summary bars:  free-wired 25 · free-unwired 73 · paid 20 · none 24         │
├───────────────────────────────────────────────────────────────────────────┤
│              flow  price  prod/area  phyto  forecast  retail  identity      │
│ Chile        ✅●   ✅●    ✅●        ✅●    🟢       —       💷            │
│ Peru         ✅●   ✅●    ✅●        🟢     ✅●      —       💷            │
│ Spain        ✅    ✅     ✅●(FAO)   ⛔     🟢       —       💷            │
│ …            (cell: ✅wired 🟢free-unwired 💷paid ⛔none; click→source)     │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Chart catalog (exact)

`avail`: **now** = committed today · **next** = after the next runner regen (both-flows
bilateral / fuller history) · **deep** = only the UK/Chile/Peru reference sources.

| # | View | Title | Type | Source · columns | Encoding | Analyst question | avail |
|---|------|-------|------|------------------|----------|------------------|-------|
| C1 | Year | **The Relay** | stacked area | `comtrade_monthly` · month, exporter, net_kg | x=month, y=share% world vol, series=top6 origins; hover $/kg | who supplies when | now |
| C2 | Year | Exporter ladder | h-bar + Δ | `comtrade_global_ranking` (role=exporter, 2 yrs) · country,value_usd,share,unit | bar=value, label share% + Δpp + $/kg | who leads, who's moving | now |
| C3 | Year | Importer ladder | h-bar + Δ | ranking (role=importer) | same | where demand is | now |
| C4 | Year | Production ≠ exports | scatter | `faostat`(production_t,yield) × ranking(value) | x=prod, y=exp value, r=yield, label hubs | grow vs ship vs re-export | now |
| C5 | Year | World map | choropleth | ranking · country,value_usd (+iso via `country_codes`) | colour=value; toggle exp/imp | the global shape | now |
| C6 | Lanes | Lane over time | dual line | `comtrade_bilateral` · exporter,importer,year,unit_usd_kg,net_kg,provisional | $/kg + volume; hatch provisional | a lane's trajectory | now (exp side) |
| C7 | Lanes | Who pays what into X | ranked bar | bilateral filter importer=X · exporter,unit_usd_kg,net_kg | $/kg ranked, width=vol | cheapest/premium origin | next (import side) |
| C8 | Lanes | Lane seasonality | line | `comtrade_monthly` · exporter,importer,month,unit,net_kg | monthly $/kg + vol arc | when + price arc | now |
| C9 | Lanes | Mirror gap | stat/badge | `comtrade_matrix.mirror_check` | exp-reported ÷ imp-reported | data trust | next |
| C10 | Lanes | Freight wedge | grouped bar | `origin_export_prices`,`netback` (FOB vs CIF) | FOB · CIF · gap $/kg | margin in transit | deep |
| C11 | Country | Export destinations | h-bar + $/kg | bilateral filter exporter=C | bar=vol, label $/kg | where it sells | now |
| C12 | Country | Import origins | h-bar + $/kg | bilateral filter importer=C | bar=vol, label $/kg | where it buys | next |
| C13 | Country | Seasonality | area | `comtrade_monthly` exporter=C | monthly export share | its supply window | now |
| C14 | Country | Production/area/yield | multi-line | `faostat` country | area_ha · production_t · yield_t_ha | growing trajectory | now |
| C15 | Country | Forecast callout | stat | `usda_forecasts` country | prod/exp/imp MT + year | the forward number | now (PE,MX) |
| C16 | Country | Climate / frost | line | `weather_regions` origin=C | tmin/t2m monthly + frost@0 | frost/heat risk | now (14 regions) |
| C17 | Country | Coverage card | stacked bar | `registry` country | counts free-wired/free/paid/none + gaps | what's knowable here | now |
| C18 | Atlas | Coverage matrix | heat-grid | `registry` · country×data-point→access,wired | ✅🟢💷⛔ cells, click→source | the moat | now |
| C19 | Atlas | Ceiling bars | bar | registry · access×wired | free-ceiling / paid / gap totals | the free frontier | now |

EU lanes (`eurostat_blueberry.csv`, EUR/kg) feed C6/C7/C11/C12 for EU members as a
cross-check / finer (CN8) alternative to Comtrade HS6.

---

## 5. Data contract — `docs/data/atlas.json`

One committed artifact the static site reads; emitted by `scripts/build_atlas_json.py`
from the CSVs, provenance-stamped. Sketch:

```json
{
  "meta": {"commodity":"blueberry","hs6":"081040","generated":"2026-06-19",
           "latest_final_year":2023,"provisional_years":[2024,2025]},
  "rankings": {"exporter":[{"year":2023,"country":"Peru","value_usd":1.68e9,
                            "share":0.328,"d_share_pp":1.0,"unit_usd_kg":7.8,"prov":false}],
               "importer":[...]},
  "relay":   [{"month":9,"shares":{"Peru":0.57,"Chile":0.0,"USA":0.13,...}}],
  "lanes":   [{"exporter":"Peru","importer":"USA","year":2023,
               "value_usd":9.57e8,"net_kg":1.13e8,"usd_kg":8.49,"flow":"exporter","prov":false}],
  "lanes_monthly":[{"exporter":"Peru","importer":"USA","year":2023,"month":9,"usd_kg":7.9}],
  "production":[{"country":"Peru","year":2023,"area_ha":...,"production_t":...,"yield":...}],
  "weather": [{"origin":"Peru","region":"La Libertad","month":7,"tmin":9.6,"t2m":17.3}],
  "forecasts":[{"country":"Mexico","metric":"production","year":2025,"value_mt":73500}],
  "registry":[{"country":"Chile","role":"exporter","data_point":"...","access":"free",
               "wired":"yes","source":"...","url":"...","verified_date":"2026-06-19"}],
  "sources": {"comtrade":{"name":"UN Comtrade","access":"free","cadence":"annual"}, ...}
}
```

Every chart binds to one of these arrays. The JSON *is* the API; a future native/3rd-party
consumer reads the same file. Keep it < a few MB (drop deep history tails the UI doesn't show).

---

## 6. Visual system

- **Access semantics (one palette everywhere):** `✅ free+wired` solid green · `🟢 free-unwired`
  hollow green · `💷 paid` amber · `⛔ none` grey. Used in the matrix, coverage cards, legends.
- **Provisional:** hatched fill + "(provisional)" tag; excluded from headline KPIs.
- **$/kg scale:** single sequential ramp reused on every price chart (e.g. 2→14 $/kg) so
  colour means the same price everywhere.
- **Deltas:** ▲ green / ▼ red, with magnitude (pp for share, % for value/price).
- **Density:** tables default-visible (analysts read tables); charts annotate directly
  (no separate legends where a label fits on the mark).

---

## 7. Provenance stamp (on every chart)

`Source · cadence · year(status) · access · verified` →
e.g. **`UN Comtrade · annual · 2023 (final) · free · ✓2026-06-19`**.
Click → the registry row (source, url, granularity, notes). A chart without a stamp ships broken.

---

## 8. Interaction & state

- **URL-encoded state** (shareable): `?commodity=blueberry&year=2023&view=lanes&from=PE&to=US`.
- **Selectors:** commodity, year (global); from/to (lanes); country (profile); role/access (atlas).
- **Copy-CSV** on every table; **download `atlas.json`** linked from the footer.
- **Cross-links:** ladder bar → country profile; coverage-card → Atlas filtered to that country;
  matrix cell → source.

---

## 9. Build order & acceptance (when we go)

1. `build_atlas_json.py` → `docs/data/atlas.json` (+ a JSON-shape test). *AC: every array
   populated from committed CSVs, provenance block present.*
2. **The Year** (C1–C5). *AC: relay matches `comtrade_monthly`; KPIs exclude provisional.*
3. **Lanes & Prices** (C6–C10). *AC: any from/to renders; provisional hatched; mirror shown when avail.*
4. **Country profiles** (C11–C17) + coverage card. *AC: every target-set country resolves; stamps present.*
5. **The Atlas** (C18–C19). *AC: 162 rows render; cell→source; filters work.*
6. **Commodity selector** + fold in UK/Chile/Peru editorial as Deep Dive.

Each view is a static section reading `atlas.json`; the Monday cron regenerates data → JSON → site.

---

## 10. Non-goals (v1) & open questions

**Non-goals:** live/real-time data; user accounts; server/API; predictive modelling beyond the
existing nowcast; importer monthly-intake seasonality (monthly is export-side only — needs a
flow=M monthly pull first).

**Open questions for sign-off:**
- **Charting tech:** keep narrative heroes as matplotlib PNGs + interactive tables/maps in
  light JS (recommended), or go fully interactive JS (e.g. Plot/ECharts) for all charts?
- **Map dependency:** a world choropleth needs a topojson + a tiny lib — acceptable, or
  start map-free (ladders + relay only) and add the map in a fast-follow?
- **Scope of v1 country profiles:** the 95% target-set (~30 countries) or just the top ~12 to start?
