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

## 2. Immediate next step (Phase 0 + 1)

1. **Registry schema** — a machine-readable atlas table (CSV/parquet), the real deliverable:
   `commodity · hs_code · country · role(exporter/importer) · data_point · access(free|paid|none) · source · url · granularity · depth · verified_date`.
   Markdown baselines (`baseline_*.md`) don't scale to global × multi-fruit — replace with this.
2. **HS-code registry** — `commodity → HS6 + national CN8/CN10 splits`. The join key for the
   whole atlas and for the other-fruit extension. (Blueberry = HS 081040; UK CN8 08104050.)
3. **Comtrade global sweep + ranking** — rank all blueberry exporters & importers by value
   → defines the "global" target set (e.g. cover countries making up 95% of trade) and
   populates every lane's flow+price at once. `comtrade.py` already fetches any reporter.

Then **Phase 2** (catalogue national overlays per country — *probe reachability, don't
wire*), **Phase 3** (deepen selectively), **Phase 4** (swap HS code for other fruits).
Full reasoning in the chat that produced this; condensed in `SOURCES.md` / `DATA.md`.

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
