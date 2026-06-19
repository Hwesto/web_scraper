# Scope: Tier-2 Sentinel-2 blueberry crop-condition index

**Goal.** A free, back-testable **Chilean blueberry crop-condition index** from Sentinel-2
(10 m), validated against Chile→UK exports — and built so the *same pipeline ports to
origins that publish no orchard/customs data* (Peru, Morocco, South Africa, Mexico).

**Why Tier 2, not Tier 3.** No ML / per-field classification yet. We compute a *regional*
condition index over the comunas Catastro already tells us are blueberry-heavy, area-
weighted. Field-level "recognise only blueberry" classification (Tier 3) is gated on this
tier first proving the satellite→export link is real. Cheap test before the big build.

---

## Data access — VERIFIED reachable (2026-06)

| Piece | Choice | Status |
|---|---|---|
| Scene index | Element84 **Earth Search** STAC (`earth-search.aws.element84.com/v1`) | ✅ reachable here — 3 S2 scenes returned over the Ñuble bbox, Jan 2024 |
| Pixels | `sentinel-cogs` public S3 COGs (red B04, nir B08, SCL) | ✅ no-auth hrefs present; windowed reads via `rioxarray`/`/vsicurl` (test under sandbox egress; else cron) |
| Cloud/shadow mask | Sentinel-2 **SCL** band | per-scene |
| Cropland mask (optional) | ESA **WorldCover** 10 m (free) | reduces non-blueberry dilution without ML |
| History | Sentinel-2 L2A ~2017→now | **~7–8 growing seasons** |
| New deps | `pystac-client`, `rioxarray`/`odc-stac`, `rasterio`, `numpy` | free |

NDVI = (B08 − B04)/(B08 + B04), SCL-masked.

## Method (pipeline)

1. **AOIs from Catastro.** We hold blueberry hectares by *comuna* (`catastro`). Take the
   blueberry-heavy comunas; weight each by its hectares. Comuna boundaries: free (BCN
   Chile / GADM) or bbox approximations.
2. **Per season × comuna.** Growing window ≈ **Oct–Mar**. Pull S2 scenes, SCL-mask cloud/
   shadow, compute NDVI per scene, aggregate to a seasonal metric — **peak NDVI** and
   **integrated "greenness-days"** (area under the seasonal curve).
3. **(Refinement) cropland-restrict** with WorldCover so the metric isn't diluted by city/
   forest/pasture. Still *not* field-level blueberry ID — that's Tier 3.
4. **National index** = hectare-weighted mean across blueberry comunas, one value/season.

## Backtest (the whole point)

Target series we already hold: **Chile→UK exports** (HMRC + DUS, multi-season) and the
**Catastro capacity baseline** (`capacity.py`, planting-age × yield).

- Test A: does the seasonal index track **export volume** (rank correlation, right sign)?
- Test B — the real test: does it explain the **residual** of exports vs the capacity
  baseline? Capacity says what the orchards *could* bear; satellite condition should
  capture the year a frost / drought / poor bloom makes them under-deliver.
- Validation: leave-one-season-out; report **effect size + CI**, not p-values.

## What we reuse (not starting from zero)

- **Catastro** → comuna AOIs + hectare weights + area validation.
- **capacity.py** → the structural baseline the index is tested *against*.
- **HMRC/DUS exports** → the target.
- **SignalSource + vintage store** → drop-in (`nowcast/data/sentinel_ndvi.py`).

## Portability — the payoff

The pipeline is **AOI-swappable**: point it at Peru's (Lambayeque/La Libertad), Morocco's
(Loukkos), or South Africa's berry regions and it runs identically — the satellite layer
is lane-independent in a way even HMRC isn't. Calibration travels imperfectly (variety,
density, climate, polytunnels differ) — flag and re-validate per region.

## Risks / honest limits

1. **n ≈ 7–8 seasons** — low statistical power. *The* caveat. Treat results as indicative;
   no over-fitting, report uncertainty.
2. **Comuna-level, not field-level** — dilution by other crops. Tier 3 (ML + training
   polygons, ~weeks) fixes this; not now.
3. **NDVI → yield is relative**, not absolute tonnage — a condition modifier, not a scale.
4. **Cloud** — central valley mostly clear; the wet south worse. SCL masking + multi-scene
   compositing mitigates.
5. **Compute/egress** — windowed COG reads are modest, but all-comuna × 8 seasons × 5-day
   revisit is a batch job → run in cron, cache per scene. Confirm `/vsicurl` S3 reads work
   under sandbox egress in Phase 2a; if blocked, it's a cron-only build (like the others).

## Phasing & decision gates

- **Phase 2a — signal probe (≈ days).** 2–3 top blueberry comunas, peak-season NDVI, all
  ~8 seasons, quick backtest vs exports + capacity residual. Minimal deps.
  **Gate:** continue only if the index shows a real, correctly-signed link (define a
  threshold up front, e.g. leave-one-out rank-corr with export residual ≥ ~0.5).
- **Phase 2b — full index (≈ week).** All blueberry comunas, WorldCover cropland mask,
  integrated seasonal metric, area-weighted national index → `SignalSource` + vintage +
  a dashboard block (Chile→UK), cron-wired.
- **Tier 3 — field classification.** Only if 2a/2b prove the signal is worth the ML build.

## Deliverables

`nowcast/data/sentinel_ndvi.py` (SignalSource) · a backtest diagnostic (index vs export
residual, leave-one-out) · a one-page GO/NO-GO memo on signal strength after Phase 2a.

> Standing rule honoured: STAC access verified before scoping; S3 COG pixel reads to be
> verified in Phase 2a before any pipeline build.

---

## Phase 2a — RESULT (probe run: `scripts/sentinel_probe.py`)

**Egress (the open question): solved in-sandbox.** GDAL/rasterio COG reads are blocked
here — the egress proxy MITMs S3 with a self-signed cert, the rasterio wheel's bundled
libcurl ignores `CURL_CA_BUNDLE`/`GDAL_HTTP_CABUNDLE`, and disabling verification is
(correctly) denied. But `urllib`/`requests`/`aiohttp` trust the egress CA, so reading COG
overviews via **`tifffile` + `fsspec`** works. No GDAL, no cron dependency for reads.
*(deps: tifffile, imagecodecs, fsspec, aiohttp, pyproj.)*

**Method (crude on purpose).** 3 AOIs (Ñuble/Chillán, Bío Bío/Los Ángeles, Maule/Linares),
least-cloudy Dec–Feb scene, ~80 m overview, SCL-masked median NDVI, AOI-mean per season.
Target: Chile→UK arrivals Jan–Apr (HMRC).

| season-end | NDVI | UK-Chile Jan–Apr (t) |
|---|---|---|
| 2019 | 0.565 | 8,115 |
| 2020 | 0.505 | 6,124 |
| 2021 | 0.542 | 8,495 |
| 2022 | 0.307 | 6,092 |
| 2023 | 0.496 | 5,878 |
| 2024 | 0.501 | 5,952 |
| 2025 | 0.532 | 5,305 |
| 2026 | 0.517 | 5,525 |

- Test A (raw exports): Spearman **+0.31** — weak (raw volume is dominated by Chile's
  structural decline, which NDVI shouldn't track).
- Test B (detrended residual — the condition test): Spearman **+0.83** (Pearson +0.42);
  **+0.71 excluding the 2022 low-NDVI outlier** (n=7). The year-to-year vigour wiggle
  tracks the year-to-year export wiggle.

**Verdict: cautious GO.** The signal shows up on the *correct* test, survives outlier
removal. Honest caveats: **n=8 low power**; researcher df (detrend / inspect 2022); crude
single-scene/coarse/unmasked probe.

### Manual scene check (2022 anomaly + control 2021)

Pulled every Dec–Feb scene per AOI with cloud%, clear-pixel count, NDVI:

- **2022 is NOT cloud contamination.** Scenes are **0 % cloud, ~35,700/35,700 clear px**;
  NDVI is genuinely ~0.24–0.35 across all three regions (vs ~0.42–0.65 in 2021). The low
  is real reflectance.
- **But three problems surface, not one:**
  1. **Heavy non-orchard dilution.** Absolute NDVI 0.24–0.65 is far below healthy
     blueberry canopy (~0.6–0.8) → the AOI box is dominated by inter-row soil / rainfed
     pasture / town, so it's a *regional* vegetation signal, not blueberry-specific.
  2. **Single-scene picking is timing-fragile.** Ñuble swung 0.39 (Jan 23) → 0.24 (Feb 7)
     within 2022; and the big *2023* heat/fire event (Jan–Feb 2023, Ñuble/Biobío) doesn't
     show — the probe grabbed a pre-fire clear scene, so season-2023 reads normal.
  3. So 2022's low is real regional dryness, but its link to *blueberry yield* is
     plausible-not-proven — the correlation may be riding regional climate, not orchards.

Net: the cautious GO holds (the correlation isn't a cloud artifact), but 2a can't yet
separate "blueberry condition" from "regional climate." That separation is the whole job
of 2b.

**→ Proceed to Phase 2b**, scoped below.

---

## Phase 2b — scope (refined by 2a)

**Objective.** Turn the regional NDVI proxy into a *blueberry-orchard* condition index and
re-test it properly — isolating orchards from the landscape, using an integrated metric,
against the capacity residual.

| # | Task | Why (from 2a) | How (free) |
|---|---|---|---|
| 1 | **Isolate orchard pixels** | absolute NDVI shows heavy non-orchard dilution | unsupervised **NDVI-persistence mask**: perennial irrigated orchards stay green through the dry summer & across years; select pixels with high multi-year summer-min NDVI. Cross-check masked hectares vs Catastro comuna area. (WorldCover cropland as a coarse pre-filter) |
| 2 | **Whole-AOI vs masked diagnostic** | can't yet tell blueberry from regional climate | compute the export correlation for **both** whole-AOI and masked-orchard NDVI. If only whole-AOI tracks → it's regional climate (weak). If masked-orchard tracks → real orchard condition. **This is the decisive 2b test.** |
| 3 | **Integrated seasonal metric** | single-scene is timing-fragile (2022 swing; 2023 fire missed) | mean/median NDVI over *all* clear scenes Nov–Feb, or greenness-days (seasonal integral) |
| 4 | **Target = capacity residual** | raw exports are trend-dominated | regress masked seasonal NDVI on (exports − `capacity.py` expectation), leave-one-season-out |
| 5 | **All blueberry comunas, Catastro-weighted** | 3 AOIs is thin | iterate Catastro top-hectare comunas; hectare-weight |
| 6 | **Event cases as natural experiments** | sanity check | does masked NDVI dip in the 2022 dry summer / where 2023 fires burned? right place, right time? |

**Deliverables.** `nowcast/data/sentinel_ndvi.py` (SignalSource: tifffile+fsspec reader,
persistence mask, integrated metric) · a backtest diagnostic (whole-AOI vs masked vs
capacity-residual, leave-one-out) · GO/NO-GO memo for Tier 3.

**Decision gate.** Continue to Tier 3 only if **task 2** shows the *masked-orchard* index
(not just whole-AOI) tracks the capacity residual. If only the regional signal survives,
stop — we'd be modelling Chilean weather, not its blueberries.

**Honest limits unchanged.** n≈8 seasons; persistence-mask ≠ true blueberry classification
(catches all perennial orchard — cherries/other berries too); NDVI is relative condition.

**Effort.** ~3–5 focused days (reader + mask + metric + backtest), no new egress risk
(tifffile+fsspec path proven), modest compute (overview reads, cache per scene).
