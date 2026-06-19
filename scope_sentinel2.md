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
