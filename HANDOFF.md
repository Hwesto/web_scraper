# HANDOFF — for the next agent (fresh context)

Read this first. It's the orientation for picking up this project cold.

## 1. The mission (what we're actually doing)

**Map all *freely available* information on global blueberry trade, flagging every gap
where a paid resource exists (and naming it) or where no source exists at all.** Start at
the UK↔Chile lane, move outward to *truly global*, then **extend the same machine to other
fruits** (HS code is just a parameter).

### Decision made this session — read carefully
We reframed the approach. There are two different deliverables and they'd been conflated:
- **The atlas** = a structured catalogue of *what information exists* (free / paid / none),
  per country × data-point × commodity. This is the actual objective. Cheap, broad.
- **The product** = live pipelines + dashboard + models. Expensive, narrow. We over-built
  this for 2 lanes (Chile, Peru) before mapping breadth.

**Go atlas-first (breadth), product-second (depth only where it pays).** The Chile/Peru
build is the proof-of-depth *reference*, not the template for grinding 15 more lanes.

**Key insight:** UN Comtrade *is* the free global base layer — bilateral volume+value for
**every exporter × every importer × HS 081040**, annual (monthly for many reporters). The
entire global flow+price matrix is one source. Everything else (producer identity, orchard
structure, variety, phyto, retail, demand, sub-monthly) is an **overlay** on specific cells.
So "global" is a Comtrade sweep, not lane-by-lane labour.

## 2. Immediate next step

**Phase 0 + 1 are DONE** (this session) — see the new `atlas/` package:
1. ✅ **Registry schema + seed** — `atlas/schema.py` + `atlas/registry.py` →
   `data/atlas/registry.csv` (68 rows). The machine-readable atlas:
   `commodity · hs_code · country · role · data_point · access(free|paid|none) · wired · source · url · granularity · depth · verified_date · notes`.
   Seeded by transcribing `baseline_*.md` (Chile deep, Peru, UK importer side, global). Query
   with `registry.gaps(access=…, wired=…)` and `registry.coverage()`. This supersedes the
   markdown baselines as the scalable atlas (baselines kept as the prose reference).
2. ✅ **HS-code registry** — `atlas/hs_codes.py` → `data/atlas/hs_codes.csv`. `commodity →
   HS6 + national CN8/HTS10 splits` (blueberry verified: HS 081040, UK CN8 08104050; other
   fruits seeded as HS6 for the Phase-4 swap, marked `verified=no`).
3. ✅ **Comtrade global sweep + ranking** — `atlas/comtrade_sweep.py` →
   `data/atlas/comtrade_global_ranking.csv`. One call per flow (`reporterCode=` empty,
   `partnerCode=0`, **`partner2Code=0`** — see below) ranks every exporter & importer by
   value. `target_set(role)` returns the ~95%-of-trade set (2023 final: **16 exporters** led
   by Peru 33%; **26 importers** led by USA 35%, UK #4). `atlas/countries.py` is the M49→name map.

**Phase 1 gotchas learned (do NOT relearn):**
- The empty-reporter preview also returns **per-secondary-partner (`partner2Code`) breakdown
  rows**, which blow past the **500-row cap** and *silently truncate* big reporters (the USA,
  #1 importer, vanished). Pin **`partner2Code=0`** → one aggregate row per reporter, uncapped.
- Comtrade annual data is **staggered**: the latest ~2 years are provisional (in mid-2026 the
  2024 sweep still missed Peru, rank 50; 2023 was complete). `comtrade_sweep.FINAL_LAG_YEARS=3`;
  `ranking`/`target_set` default to the latest **non-provisional** year.

**Phase 2 STARTED** — national overlays catalogued for the 8 top exporters beyond
the Chile/Peru reference lanes (**Spain, Netherlands, Morocco, USA, Mexico, Canada,
South Africa, Poland**), 40 rows added (registry now 109). Per country, 4-5 overlay
categories probed for reachability (`atlas/probe.py` — classifies reachable /
key_gated / auth / tls_blocked etc., handling the "200 + Missing Key" case). Findings:
- **No country publishes free shipment-level export data with exporter names** — that
  identity layer is paid (brokers) everywhere, same gap as Chile/Peru.
- **Free NPPO orchard rosters exist for Mexico (SENASICA) and Morocco (ONSSA)** — the
  SAG-China analogue; Spain/NL/USA/Canada/Poland keep theirs gated (`access=none`).
- **Free orchard/area census exists for all 8** (ESYRCE, NASS QuickStats, SIAP, StatCan,
  Berries ZA, etc.) — Catastro analogues of varying granularity.
- **Eurostat COMEXT** = the free harmonised CN8 overlay for all EU exporters (one global row).
- Sandbox-blocked (503/anti-bot, real sources): StatCan CIMT, PL GUS/PIORIN, MA ONSSA,
  MX SIAP, MA Office des Changes — **re-probe on the clean-egress runner** (`verified_date`
  left blank for these). Query: `registry.gaps(access=…, wired=…)`.

**Phase 2b DONE** — importer-side + re-export-hub overlays for **Germany, France, China,
Hong Kong, Switzerland, South Korea, Japan, Belgium, Portugal, Italy, Austria, Serbia**
(registry now **141 rows**). Findings: **Hong Kong is the only stats system with a clean
re-export flow split** (EU/DE/FR fold re-exports into total exports — hub activity must be
inferred); **China CIFER** is a free registered-overseas-producer query; **no NPPO publishes
a per-fruit blueberry approved-orchard list** (USDA-FAS GAIN is the best free who-ships-where
summary); domestic blueberry area is official for PT/DE/KR, industry-sourced for IT/RS/CN.

**Runner re-probe wired** — `.github/workflows/atlas-refresh.yml` (Mon 06:41 UTC + dispatch)
runs on the clean-egress runner: refreshes the Comtrade global ranking and re-probes every
catalogued source via `scripts/probe_overlays.py` → `data/atlas/probe_log.csv` (the live
reachability record, kept separate from the seed-generated `registry.csv`). `atlas/probe.py`
classifies reachable/key_gated/auth/tls_blocked and normalises bare hostnames. From the
sandbox 49/84 sources resolve; the rest (StatCan CIMT, DE Destatis, HK Trade IDDS, MA ONSSA,
MX SIAP, PL GUS, AT STATcube, CN GACC, KR APQA/KOSIS, ...) are anti-bot/503 here and should
firm up on the runner.

**Still to do:** **Phase 3** (deepen selectively where it pays — e.g. wire a high-value free
overlay like Mexico SENASICA or Eurostat COMEXT); **Phase 4** (swap HS code for other fruits —
`hs_codes.csv` already seeded). Full reasoning condensed in `SOURCES.md` / `DATA.md`.

## 3. Where things stand

- **Lanes built (deep):** Chile→UK (flow, named producers, varieties, capacity, renewal,
  phyto, netback, nowcast) and Peru→UK (netback, USDA forward outlook, seasonality).
- **Data depth:** uniform **2018→present** on core series; Comtrade 2012→25; Catastro 1987.
- **Dashboard:** `docs/index.html` — a comparison view (exporter×importer dropdowns +
  coverage matrix), 17 blocks, built by `scripts/build_static_dashboard.py`, served on Pages.
- **Atlas docs so far:** `SOURCES.md` (source link list), `DATA.md` (data-point × link ×
  renewal), `baseline_chile-uk.md` / `baseline_peru-uk.md` (per-lane gap maps),
  `scope_sentinel2.md` (satellite Tier-2 scope + 2a probe result).

## 4. Repo map

- `atlas/` — **the breadth-first deliverable (Phase 0/1)**: `schema.py` (registry columns +
  `validate`), `registry.py` (`seed`/`load`/`gaps`/`coverage`), `hs_codes.py` (commodity→HS6
  + national splits), `comtrade_sweep.py` (global exporter/importer ranking + `target_set`),
  `countries.py` (M49↔name). Reads/writes `data/atlas/*.csv`. Tests: `tests/test_atlas.py`.
- `nowcast/data/` — SignalSources (HMRC, DEFRA, ONS, retail, NDVI, job_boards) + `base.py`
  (tidy schema) ; `nowcast/store/vintage.py` — append-only vintage store (look-ahead-free).
- `nowcast/market/` — `comtrade.py` (destinations, any reporter), `origin_prices.py`
  (export FOB + FOB→CIF wedge), `netback.py` (origin-aware), `fx.py`, `asia_access.py`.
- `nowcast/farm/` — `catastro.py`→`capacity.py` (orchard area→bearing capacity), `sag_china.py`
  (phyto roster), `names.py` (entity matching), `certs.py`.
- `nowcast/volume/`, `nowcast/model/`, `nowcast/backtest/` — the volume nowcast stack.
- `scripts/` — `fetch_chile_weekly_exports.py`, `fetch_sag_china.py`, `fetch_usda_peru.py`,
  `sentinel_probe.py`, `build_static_dashboard.py`.
- `data/` — `weekly/` (Chile), `market/` (Comtrade caches, fx, peru_fundamentals, sag),
  `vintages/<series>/<date>.parquet`, `farm/` (catastro parquet).
- `.github/workflows/chile-weekly-exports.yml` — the only workflow. Monday 06:17 UTC,
  `mode=collect`. Runs: Chile DUS → comtrade (Chile+Peru) → origin_prices → fx → sag →
  **`pipeline ingest`** (HMRC/DEFRA/ODEPA/ONS/retail) → dashboard → commit.
- Tests: `tests/` — 64 passing; `python -m pytest -q`.

## 5. Hard-won gotchas (do NOT relearn these)

- **Sandbox egress is MITM/selective.** From the Claude sandbox: `datos.gob.cl` is
  TLS-blocked; S3 (`sentinel-cogs`) is MITM'd (self-signed) — GDAL's bundled libcurl
  rejects it and **disabling TLS verification is denied by policy**. Reads that work:
  `urllib`/`requests`/`tifffile+fsspec` (they trust the system CA at
  `/etc/ssl/certs/ca-certificates.crt`). **Comtrade, gov.uk, ONS, SAG, USDA, Frankfurter
  reachable.** Anything blocked here usually works on the **GitHub runner (clean egress)** —
  that's why fetchers run in the cron.
- **Comtrade preview returns DUPLICATE rows** — dedup on (year, partner_code). Already done
  in `comtrade.py`; remember it for any new Comtrade code.
- **ORNL MODIS API throttles** bulk sequential pulls (NDVI). Single points work cold.
- **Tiny-N unit values lie** — filter customs lanes by volume (≥200–250 t) before trusting
  $/kg; Comtrade *revises* small lanes heavily (Spain→UK went 5,230 t → 17.6 t).
- **PDF parsing** (USDA): anchor table extraction on the specific header row, not "first
  match" — other tables share year tokens.
- **Peru has no Catastro** (no per-block orchard census, no cultivar-per-shipment). USDA-FAS
  annual is its structural substitute. Expect this asymmetry per country.

## 6. Working conventions

- **Verify a source is reachable/parseable before building on it** (standing rule).
- **Never fabricate data** — degrade to empty/fallback and say so. Document every assumption
  inline (e.g. freight constants, FX notional fallback).
- **Honesty in reporting** — state caveats, n, what's estimate vs measured.
- Branch: was `claude/uk-blueberry-nowcast-fusion-35bvjt`; now merged to `main`. Commit with
  clear messages; tests green before commit; push.
- Dashboard blocks are tagged `(exporter, importer, source)`; empty matrix cells are honest
  gaps. Keep that discipline.

## 7. Open threads (lower priority)
- NDVI is the only series still manual/off-cron (throttle-flaky; parked).
- Sentinel-2 Tier-2 is a `PROBE` (cautious GO; not pipelined) — see `scope_sentinel2.md`.
- ProArándanos weekly (Peru) has no structured free feed (press/PDF only).
- USDA `REPORT_URL` needs a manual bump when the next annual publishes.

**Start with Phase 0/1 (registry schema + HS table + Comtrade global ranking).** That's the
foundation the whole atlas hangs off, and it's mostly cataloguing, not building.
