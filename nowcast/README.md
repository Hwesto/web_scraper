# UK Blueberry Hidden-Flow Nowcast

Estimating the opaque EU/Morocco -> UK blueberry import flow weekly and in real
time, ahead of HMRC's ~6-week-lagged monthly print, by fusing free signals into
a mixed-frequency state-space (Kalman) model.

This README tracks **what is actually built and verified**, not the full vision.
The full design and the data-source stress test live in the project discussion.

## Status

| Milestone | What | State |
|---|---|---|
| **M1** | Real data ingest + append-only vintage store | **done, real data** |
| **M2** | Volume-space state-space + Kalman + MLE calibration | **done, real data** |
| **M3** | Walk-forward backtest vs seasonal-naive / persistence / ARIMA | **done — gate NOT passed** |
| **M4a** | Retail price fusion (ONS year-round price, 2nd observation) | **done — no gate lift** |
| **M4b** | Satellite NDVI leading-signal test (MODIS) | **done — does not lead volume** |
| M5 | Forward-collect (packhouse hiring + live retail price) | stubs wired |

**M3 is the gate:** ship nothing until it provably beats seasonal-naive at a
useful lead. Alt-data (M5) never counts toward this gate — it has no history.

### M3 verdict (honest): HMRC-only does NOT beat seasonal-naive

Walk-forward backtest, K=3, 2024-2026 out-of-sample (`python3 -m nowcast.pipeline
backtest Morocco`). Skill = % MAE improvement vs benchmark (positive = better):

| Origin | h=1 vs seasonal-naive | vs ARIMA | dir. skill | verdict |
|---|---|---|---|---|
| Morocco | **-22.5%** | +13.0% | 74% | FAIL gate |
| Spain | -101.6% | -14.8% | 65% | FAIL gate |

Findings:
- The blueberry import series is so dominated by stable annual seasonality that
  **seasonal-naive is a very strong benchmark**; HMRC-only structural modelling
  beats ARIMA but cannot beat seasonal-naive at any horizon. Per the spec's own
  bar, that means "we have nothing" *yet* on free monthly data alone.
- **A spurious +37% Morocco "win" appeared first** because Morocco's near-zero
  off-season months are simply absent from HMRC, so the model was only tested on
  high-volume in-season months. Zero-filling those months (now the default in
  `load_origin_series`) removed the selection bias. The backtest doing its job
  and catching this is the point.
- Implication (confirms the design stress test): the alpha **requires genuinely
  leading signals** (in-season retail price, satellite, origin), not better
  modelling of HMRC. Next real step is to bring those in — which is why the
  alt-data clock was started in M1.
- Secondary positive: directional skill ~74% and the model decisively beats
  ARIMA, so the structure is informative — just not enough to clear seasonal-naive.

### M4a verdict (honest): retail price fusion does NOT lift the gate

We found a genuinely free, *year-round* historical retail blueberry price (ONS
Shopping Prices Comparison Tool, item 212733, monthly GBP/kg, 2018-01..2025-01)
— unlike DEFRA wholesale, it exists in the Dec-May import season. We fused it as
a second observation (`price = alpha + beta*volume + eps`, beta calibrated on the
training window) via a generalised multi-observation Kalman update, and added a
nowcast mode that uses HMRC through month t-1 plus the contemporaneous price for
month t (modelling HMRC's ~6-week lag).

Result, real-data nowcast backtest (`run_nowcast_backtest`):
- Adding price changes nowcast MAE by **~0%** (Morocco -0.2%, Spain -0.0%).
- Both still lose to seasonal-naive (Morocco -76%, Spain -144%).

Why (diagnosed, not assumed): the ONS price anomaly correlates with the import
volume anomaly only weakly and contemporaneously (r about -0.13 to -0.21, correct
sign) and **does not lead it** (lead correlations are noise). Retail consumer
prices are sticky, marked up and demand-driven, so they carry little timely
information about import supply.

Proof the null is real, not a broken pipe: `tests/test_price_fusion.py` injects a
*strong* synthetic price signal and confirms the same fusion code then cuts
nowcast error by >20% and recovers the negative beta. The mechanism works; the
free retail price simply isn't informative enough.

Implication: a price signal worth fusing would need to be a *leading*,
supply-side price (FOB origin / wholesale-at-origin), which is not free. The
remaining free lever is the forward forecast (NDVI, M4b) and forward-collected
leading signals (M5) — neither of which can be validated until a season accrues.

### M4b verdict (honest): satellite NDVI does not lead import volume

NDVI is the only free signal that is *structurally* leading (crop greenness
precedes shipment), so it got the same lead-correlation diagnostic. Free MODIS
MOD13Q1 (250m, 16-day) over Huelva and Larache, 2018-2024, vs origin volume
anomaly (n about 70):

| Region -> origin | contemp | lead-1 | lead-2 | lead-3 |
|---|---|---|---|---|
| Huelva -> Spain | -0.05 | -0.03 | -0.11 | **-0.23** |
| Larache -> Morocco | 0.06 | 0.13 | 0.11 | 0.07 |

No correctly-signed, significant leading relationship. The strongest correlation
(Huelva lead-3, -0.23) has the **wrong sign** (more greenness -> less volume) and
is only borderline at n=69 — consistent with the known confound: Huelva/Larache
berries grow under poly/macro-tunnels that mask the canopy, and a few-km box
mixes in other land cover. NDVI here does not cleanly track the berry crop, so it
carries no usable leading signal. Fusion was therefore not built (it would
reproduce the price null); the NDVI series is still ingested and stored.

## Overall conclusion (free-data tier)

Three independent free signals were tested against the seasonal-naive gate:

| Signal | Role | Result |
|---|---|---|
| HMRC structural model (M3) | trend + seasonal | beats ARIMA, **loses to seasonal-naive** |
| ONS retail price (M4a) | coincident price | fusion lifts gate **~0%** |
| MODIS NDVI (M4b) | leading crop proxy | **does not lead** volume |

The blueberry import series is dominated by stable seasonality plus Morocco's
trend — both of which seasonal-naive (per origin) already captures well. Every
free signal we can obtain is coincident/lagging (price), structurally masked
(NDVI under tunnels) or already inside HMRC (trend/seasonal). **On free data
alone, this flow is not nowcastable beyond seasonal-naive.** This is a clean,
evidenced negative — and it matches the up-front data stress test: the alpha
requires a genuinely *leading* signal, and every such signal here is paid
(FOB/at-origin price, historical AIS, Kantar) or only accrues forward (M5).

What would change the verdict: a paid leading supply-side price, or ~1-2 seasons
of forward-collected packhouse-hiring / live-retail data (clocks started; run
`ingest` daily). Until then the honest product is the seasonal-naive baseline
plus the model's directional read, not a gate-beating nowcast.

---

# Part 2 — Volume construction (reconciled weekly series)

A different, *achievable* deliverable: not beating a benchmark, but building one
coherent weekly by-origin volume series (kg) that reconciles exactly to HMRC and
tags every point by how much we actually know. Code in `nowcast/volume/`.

`python3 -m nowcast.pipeline volume Morocco` (or Chile, Spain, ...).

## How it works (spec sections 1, 4, 5)
- **Control total**: HMRC monthly by origin (`data/hmrc.py`, reused).
- **Shape**: the Part 1 structural model's weekly volume path (`model/structural.py
  .weekly_volume_path`).
- **Benchmark**: proportional Denton (`volume/benchmark.py`) marries shape to
  control so weekly sums equal the HMRC month **exactly** (verified: max
  reconciliation error 0.1 kg).
- **Ragged edge**: weeks past the last HMRC print are the model nowcast with 80%
  bands (`nowcast` tier); older weeks are `aggregate_benchmarked`.
- **Output** (`volume/series.py`): the spec-section-8 record — origin, iso_week,
  volume_kg, confidence_tier, method, control_total_month_kg, band_low/high,
  vintage_date.

## Deep-sea shipment tier + validation (sections 2a, 6) — real data win
- `volume/data/odepa_chile.py`: Chile -> UK fresh-blueberry monthly exports from
  **ODEPA open data** (Servicio Nacional de Aduanas, free CKAN), net kg, 2018-2026.
- Two-sided cross-check (`volume/validate.py`): ODEPA export vs HMRC import for
  Chile agree strongly (**corr 0.92**, export/import 1.12). The 12% export>import
  gap corroborates the Netherlands-transhipment thesis (Chile fruit arriving via
  Rotterdam booked by HMRC as NL, not Chile).
- ODEPA export and HMRC import agree as a **cross-check** (corr 0.92). NOTE: an
  earlier draft over-claimed this as a "genuine leading signal" -- corrected
  below (Part 4). At monthly resolution the transit lead collapses to ~0, and the
  0.92 is largely shared seasonality; put through the turning-point gauntlet the
  genuine lead does NOT beat seasonal-naive. The 0.92 is valid as validation, not
  as a forecast edge.

## Netherlands de-convolution (section 2b)
`volume/deconvolve.py`: reattributes the re-export share of NL->UK (counter-season
months) to Peru/Chile pro-rata, conserving mass. An explicit, configurable
*heuristic* (no consignee data to measure it) — tagged so it is never shown as
observed.

## Data feasibility (free-only, verified)
| Segment | Source | Status |
|---|---|---|
| Control totals | HMRC OTS | free, done |
| Deep-sea Chile `shipment` | ODEPA (Aduanas) | free, **done** (monthly) |
| Deep-sea Peru `shipment` | SUNAT | paid (Agronometrics/Veritrade) — stub |
| Daily Chile DUS (weekly shape) | datos.gob.cl | not reachable here (503/TLS) |
| AIS arrivals | reefer AIS | paid history — stub |
| Short-sea weekly shape | Freshuelva/Foodex | not free — model shape used |
| Mirror (named consignee) | Volza/ImportGenius | paid — stub |

## Honest scope
A complete, reconciled, provenance-tagged weekly series for every origin. Tiers
are mostly `aggregate_benchmarked` + `nowcast`; the `shipment` tier is real for
**Chile** (ODEPA, monthly cross-check) but Peru/weekly-DUS/AIS remain paid or
unreachable. The series is a genuine data product — HMRC sets the level, the
model sets the shape, Denton marries them exactly, and every point says how much
is observed vs reconstructed vs modelled.

---

# Part 3 — Chile farm structure & capacity forecast (`nowcast/farm/`)

Re-aim of the Part 1 turning-point bet, grounded in real orchard structure
instead of a price series. `python3 -m nowcast.farm.forecast`.

## Source verification (proposal vs reality)
The Part 3 proposal's citations were fabricated, so each claim was checked
against the live Catastro Frutícola (CIREN-ODEPA) open data:

| Proposal claim | Verified reality |
|---|---|
| Free per-property **destination** (export/domestic) | ❌ not in the data |
| Free per-property **yield** | ❌ not in the data |
| Free **named/georeferenced** (razon social, rol, GIS) | ❌ free tier is anonymised + comuna-level; named/GIS is paid CIREN (contents unverified) |
| ODEPA customs **by exporter** | ❌ by region only (paid for exporter) |
| Per-orchard NDVI on Catastro polygons | ❌ no polygons free |
| Census on a multi-year regional rotation | ✅ true (2019/2022/2024 are the blueberry years) |
| Planting-year -> forward capacity signal | ✅ true and free — the one real prize |
| SAG export-orchard registry (free cert layer) | ❌ market-driven only (China/Mexico); **no UK blueberry list**; SAG bulk data on the blocked datos.gob.cl |

What IS free and real: per-block blueberry **area, variety, planting year,
irrigation, #trees** by comuna (`data/catastro.py`), stitched to each region's
latest survey -> ~14,000 ha, 9,232 blocks, centred on Maule/Ñuble.

## The model and its honest result
`capacity.py` applies a blueberry yield-by-vine-age curve to area-by-planting-
year -> a bearing-capacity trajectory (the season-level forward signal). `forecast.py`
tilts seasonal-naive by capacity growth and scores turning points against
realised ODEPA Chile->UK exports.

**Verdict: the capacity tilt does NOT beat seasonal-naive** (MAE 1,337 vs 1,120;
direction 50%; corr(capacity-growth, export-change) = -0.09). Reason, diagnosed:
the well-documented Chilean blueberry decline — exports to the UK fell ~10.6k ->
~6.5k t (2019-2026) while planted area kept maturing, so area-based capacity
**overpredicts**. The fix would need the per-orchard **yield/harvest-rate** field
— precisely the field the proposal wrongly claimed was free. It is not, so on
free data the structural area signal is decoupled from realised export volume.

The capacity map remains a valid **structural data product** (area/variety/age by
region); it just is not a predictive tilt for Chile in its current decline.

## Plugging the gap (the follow-up): multi-vintage area + variety
The fix targeted the two free levers we'd underused: **multi-vintage Catastro
area** (which shows the real -21% decline, 16.7k->13.2k ha 2019-2024) instead of
aging one snapshot, and a **variety fresh-UK-suitability weight** (old/soft ->
frozen; new/firm -> fresh, which matters most on long sea-freight to the UK).

Caught artefact (and corrected): a first cut scored 87.5% directional skill --
but that was spurious. The Catastro vintages have wildly different geographic
COVERAGE (2019/2022/2024 ~national; 2020/2021/2023/2025 only 1-2 regions), so a
nearest-survey index oscillated between full and partial files and was measuring
coverage, not capacity. Restricting to comprehensive years and interpolating
(`capacity.comprehensive_years` / `interpolated_capacity`, guarded by tests)
removes it.

Honest corrected result: v2 (multi-vintage + variety) is now well-behaved --
overprediction gone, MAE 1,162 vs seasonal-naive 1,120 (was 1,337) -- but still
**50% directional skill: no edge over seasonal-naive**. Reason: only 4 structural
survey anchors over 2016-2024 yield a smooth capacity curve that tracks the
multi-year decline LEVEL but cannot call the year-to-year turning points
(2021^, 2022v, 2024^, 2025v, 2026^), which are driven by weather/demand/harvest
timing, not orchard structure. Structure != turning points; the genuinely
leading signal (Committee season forecast, by-exporter weekly) is paid or
PDF-only (verified). Net Part 3: a real structural data product, not a
gate-beating forecast.

---

# Part 4 — Symmetric re-test of the origin-export "lead" (correcting our own claim)

We had labelled the Chile origin-export a "genuine positive" on a lagged
correlation of 0.92 -- without putting it through the same walk-forward
turning-point gauntlet as the four negatives. That was asymmetric rigor. Fixed
in `backtest/lead.py`: predict HMRC Chile import month M from ODEPA export, score
directional skill on the anomaly (deviation from seasonal-naive) + MAE, vs
seasonal-naive / persistence.

In-season result (n=35):
| model | MAE | dir skill | vs seasonal-naive |
|---|---|---|---|
| seasonal-naive | 460 | (0 by constr.) | 0% |
| **odepa_lag1** (mechanical voyage lead) | 829 | 57% | **-80%** |
| odepa_contemp (NOT a lead) | 418 | 63% | +9% |

Verdict: **the genuine, actionable monthly lead does NOT beat seasonal-naive**
(MAE 80% worse in-season, direction 57% ~ coin flip). The 0.92 was mostly shared
seasonality, which seasonal-naive already owns. The only positive (contemporaneous
+9% / 63%) is not a lead and is probably not even actionable -- ODEPA monthly
export carries its own ~1-2 month publish lag, so export-month M is unlikely to be
known before HMRC prints import-month M. The synthetic guard
(`tests/test_lead.py`) proves the gauntlet DOES detect a perfect lead (>70% dir),
so this negative is real, not a broken test.

Precise, earned conclusion (replacing "needs a paid leading signal"): the free
MONTHLY origin-export carries no turning-point edge, because at monthly resolution
the 3-5 week transit lead collapses to ~0. A real lead needs WEEKLY origin
resolution -- the daily Chile DUS feed (free but on the blocked datos.gob.cl) or
paid by-exporter weekly (Veritrade/Agronometrics). So: "needs finer-resolution
(weekly) origin data" -- not necessarily paid, but not the free monthly series.

## Scorecard (honest, symmetric)
- Predictive goal vs seasonal-naive: **5 clean negatives** -- HMRC-only, retail
  price, NDVI, farm capacity (near-foreordained: structure is a level signal, not
  a turning-point one), and now origin-export lead. Each diagnosed to a cause.
- **3 integrity catches** of spurious wins: Morocco +37% (selection bias),
  capacity 87.5% (survey-coverage artefact), and this asymmetric-rigor 0.92.
- **1 constructive positive**: Part 2's reconciled, confidence-tiered weekly
  volume product (and ODEPA as a valid cross-check, not a forecast).

## Weekly origin data via GitHub Actions (the resolution upgrade)

The monthly origin series had no turning-point edge because the 3-5 week transit
lead collapses at monthly resolution. The fix is WEEKLY origin data: the Aduana
DUS records (day-level FECHAACEPT) on datos.gob.cl -- free, but TLS-blocked from
this sandbox's proxy. A GitHub Actions cron solves the access problem (runners
have clean egress):

- `.github/workflows/chile-weekly-exports.yml` + `scripts/fetch_chile_weekly_exports.py`:
  download the monthly DUS `.rar`s, filter fresh blueberry (08104*) -> REINO
  UNIDO, aggregate `CANTIDADMERCANCIA` by ISO week, commit
  `data/weekly/chile_uk_blueberry_weekly.csv`. Weekly schedule keeps it current.
- Backfilled **2018-W01..2026-W13, 182 weeks** (slug varies by year:
  `registro-de-exportacion(es)-{y}`). Validated against ODEPA monthly: **median
  ratio 1.0, 88% of months within +-15%** across 56 months.
- `nowcast/volume/data/chile_weekly.py` loads it as a weekly series.

**Wired into Part 2 (done):** `volume/series.py` now uses the weekly origin
export, shifted by the deep-sea transit time (~4 weeks) to approximate UK
arrival, as the within-month SHAPE for Chile -- still Denton-reconciled to the
HMRC monthly control (max error 0.1 kg), but tagged **`shipment`** tier
(`shipment_recon`, source `HMRC-OTS;ODEPA-DUS-weekly`) instead of model-implied
`aggregate_benchmarked`. 222 of 234 Chile weeks are now shipment-shaped from real
consignments; the ragged edge stays `nowcast`. Origins without a feed (Morocco,
Spain) are unchanged (model shape). `_EXPORT_FEEDS` registers which origins have
a weekly feed and their transit lag.

This is the genuine data unlock: a free, weekly, validated origin signal with a
mechanical voyage lead, now driving the deep-sea volume shape.

# Part 5 — Within-month nowcast: the first edge over seasonal-naive

`backtest/within_month.py` runs the symmetric turning-point bar with the WEEKLY
exports: shift each export week by the transit time to its UK-arrival week,
aggregate to the arrival month, scale (train-calibrated), and predict the HMRC
Chile import print for month M. Target = HMRC (independent of the DUS predictor).

Transit sweep, in-season (n=35), MAE vs seasonal-naive (460 t):
| effective lead | origin MAE | skill vs s-naive | dir skill |
|---|---|---|---|
| 0 wk | 461 | -0.1% | 63% |
| **1 wk** | **404** | **+12.2%** | 66% |
| **2 wk** | **378** | **+18.0%** | 66% |
| 4 wk (pure forward) | 789 | -71% | 63% |

**Result: at a 1-2 week effective lead, weekly origin export BEATS seasonal-naive
(+12-18% MAE, ~66% directional vs s-naive's structural 0%)** -- the first free
signal to do so on the import anomaly. A *pure forward* forecast (transit >=4 wk,
no same-month data) still fails (-71%), consistent with everything prior: the
edge is a contemporaneous NOWCAST, not a month-ahead forecast.

Crucially, the timeliness is VERIFIED (not assumed, unlike the earlier lead test):
the Chilean DUS for month M publishes ~4 weeks after month-end (Jan->Feb 27, etc.),
while HMRC's month-M print lands ~6 weeks after -- so origin data gives a real
**~2-week actionable jump on HMRC**, beating seasonal-naive by ~15%.

Honest caveats (kept symmetric): n=35 in-season months is small; the 1-2 wk
effective lead was read off a sweep, not calibrated out-of-sample; the edge is
modest (~15%). A synthetic guard (`tests/test_within_month.py`) confirms the test
detects a real signal and none from noise.

### Out-of-sample calibration (firming up the number)

`within_month.calibrated_run` removes the sweep look-ahead: at each test month it
picks BOTH the transit lag and the scale using only data before that month. The
held-out result:

| | origin MAE | seasonal-naive | skill | dir skill |
|---|---|---|---|---|
| in-season (n=35) | 405 | 460 | **+12.0%** | 60% |
| all months (n=75) | 206 | 227 | +9.3% | 59% |

The lag selection is stable -- it picks **1 wk (40x) or 2 wk (35x)**, never the
failing 4+ wk. So the edge survives honest out-of-sample calibration at **~+12%
MAE / 60% directional**, landing at the conservative end of the in-sample range
(exactly what dropping the peek should do). Remaining caveat is just sample size
(8 seasons). This is the defensible figure: a genuine, free, ~2-week-ahead,
out-of-sample, timeliness-verified ~12% edge over seasonal-naive.

# Part 6 — Producer & cultivar trace (de-anonymising the flow)

The masked exporter RUT is not the whole story: the DUS **cargo-description**
fields leak the producer/marca and the cultivar. `scripts/fetch_chile_weekly_exports.py`
now parses them, so `data/weekly/chile_uk_blueberry_by_producer.csv` traces our
UK-bound flow to **named producers**:

- **72 named producers** (~10.0M kg, 2025-26), each with growing region + cultivar:
  HORTIFRUT (1,524 t, O'Higgins), S&A (1,421 t, Biobío, Legacy), AGROBERRIES
  (660 t, Duke), SAN RAFAEL, LAS MORAS, ANGUS (Blue Ribbon), DOLE, PATAGONIA
  (Cargo), PATRON, AGUADA, LAFRUT (Draper), REINA SUR, CUATRO VIENTOS, AGRICOLA
  CATO (Suziblue)...
- **Cultivar mix**: Legacy 1.98M kg, Duke 882k, Blue Ribbon 525k, Cargo 385k,
  Star 245k, Suziblue 243k, Draper 207k, Top Shelf 189k -- Legacy-dominant with
  the firm renewal varieties behind it (matches the variety-renewal story).

So we name producers + cultivars for free, from data we already pull -- no US
mirror match (Strategy 1) and the cultivar dimension Strategy 2 wanted, both in-hand.

Coverage (2025-26 flow): producer **named on ~91%** of kg; growing **region ~100%**;
**specific cultivar ~46%**. The 46% is a near-CEILING, not a parser gap: the
unmatched ~54% declares no single cultivar in the source -- "ARANDANOS FRESCOS",
"TRADICIONALES", "AZULES", or explicitly "DIFERENTES VARIEDADES" (mixed). An
expanded cultivar dictionary lifted it 42%->46%; the rest is unrecoverable
(cultivar simply not stated), so do not expect ~65%. Specific named+located
*orchard* stays ~5% free (USDA organic) unless matched to SAG's China list or
paid CIREN.

Honest limits (the last mile): names are messy free-text needing canonicalisation
(LAFRUT vs "LA FRUT F-"; ANGUS vs ANGUS SOFT; S&A vs COMERCIALIZADORA S&A -- the
spec's canonical_entities step); a marca is a producer/exporter brand (often a
grower-group or integrated grower-exporter), **not** a specific orchard;
coverage is partial (generic "SIN-CODIGO ~ARANDANOS FRESCOS" rows stay unnamed);
and this reflects the refreshed years (full-history producer attribution needs a
backfill -- the volume series itself is full 2018-2026). Tying a marca to a
specific **certified farm** is where free ends: GlobalG.A.P. validates per-GGN
(needs the GGNs), and orchard polygons are paid CIREN.

### Cert layer (`nowcast/farm/certs.py`) -- and why name->GGN isn't free

Verified dead-ends for a free name->GGN (or name->certified-orchard) crosswalk:
GlobalG.A.P.'s public DB validates a *known* GGN but has **no name search**;
phyto certs are per-consignment SAG/APHA docs (not public bulk; carry SAG CSG
codes, not GGNs); SAG bulk is on the TLS-blocked datos.gob.cl; GACC publishes no
clean named Chilean-blueberry orchard list (and it'd be the China-export subset);
CIREN's named directorio is paid. A GGN *is* a GS1 GLN, so GEPIR can ENRICH a
known GLN->entity -- but cannot discover it from a name.

So the free, defensible cert layer is: (1) `tag_uk_cert_status()` -- UK retail
mandates GLOBALG.A.P. for imported fresh produce (CBI/retailer policy), so every
named producer is near-certainly certified, no GGN required; (2) `attach_ggns()`
+ `validate_ggn()`/`gln_to_entity()` -- the plug-in for GGNs obtained out of band
(an importer's own supplier specs, the product GGN label, retailer disclosure),
which we then validate + enrich. We can validate a GGN; we just can't find it
from the name. Tests cover the pure status-inference and GGN-attach logic.

# Part 7 — "This week's call" (the hero panel) + whole-market

`nowcast/call.py` (`python -m nowcast.pipeline call [--date YYYY-MM-DD]`) answers
the importer's recurring decision -- **sell now / hold / lock** -- in one read:

```
THIS WEEK'S CALL  |  Chile arrivals, 2025-01
  Supply: 1852 t vs 2302 t normal = -20%  [SHORT (light)]   (validated nowcast, ~2wk lead, +12% OOS)
  Price:  12.46 GBP/kg, flat (-0% 3m)
  READ:   Light Chile arrivals + flat cost -> UK price likely up ~0% over 2-3 wks -> lock / cover now.
```

Honest construction: the **supply line is the validated within-month nowcast**
(arrivals vs seasonal norm, ~2 weeks ahead of HMRC, +12% OOS -- a *probabilistic*
60%-directional call, not a guarantee). The **price line is a transparent
inference** (supply-pressure sign + observed price trend + a flagged, low-
confidence elasticity; demand assumed stable) -- magnitudes are deliberately
small because blueberry price/volume linkage is weak, and that's surfaced rather
than inflated. Off-season it says so instead of faking a call.

**Whole-market continuity** (`volume/uk_total.py`, `build_uk_total()`): the
fused UK supply series sums every HMRC origin year-round (Morocco 28%, Peru 26%,
South Africa 14%, Chile 12%, ...), so the tool is never blank -- live shipment
shape on the deep-sea lane in season (Chile), benchmarked elsewhere. Peru verdict:
its volume is already in the total via HMRC; a Chile-style weekly nowcast + named
producers for Peru needs paid customs (SUNAT granular data is commercialised).

## Scorecard (updated)
- Predictive vs seasonal-naive: 5 negatives on monthly/structural signals; **1
  out-of-sample positive** -- the weekly origin within-month nowcast (+12% MAE,
  60% directional, ~2-wk verified lead).
- 3 integrity catches (Morocco +37%, capacity 87.5%, the 0.92).
- Constructive: Part 2 reconciled volume product, now with a Chile shipment-tier
  weekly shape from real origin consignments.

## Verified data sources (free)

- **HMRC OTS** (`data/hmrc.py`) — anchor + ground truth. Live OData API,
  CN8 `08104050` (cultivated blueberry + cranberry), `NetMass` kg -> tonnes.
  Real pull confirmed: 2018-01 .. 2026-04, 6 origins.
- **DEFRA wholesale price** (`data/defra_price.py`) — price/demand context.
  Machine-readable CSV, blueberry line, GBP/kg.

## Real-data findings (M1)

1. **Morocco is exploding**: ~1,750 t (2018) -> 18,066 t (2025), now 5-6x Spain
   and rising fast. The local-linear-trend (`level`+`slope`) state is there to
   absorb exactly this. Spain is stable (~2.5-4.8k t/yr) and cleanly seasonal,
   peaking May-Jun; Morocco peaks Jan-Apr -> anti-phase, extended import window.
2. **Strong, clean seasonality** => seasonal-naive is a stiff benchmark. The
   tradeable alpha is the *anomaly* around the seasonal norm, not the level.
3. **EU/non-EU collection seam**: Spain/PT/NL arrive via FlowType 1 (EU,
   Intrastat-derived); Morocco/Peru/Chile via FlowType 3 (non-EU, customs).
   Different methods -> a consistency seam, worst around the post-Brexit break.
4. **DEFRA price is anti-aligned with the target season**: it only quotes
   blueberries while UK home-grown is in season (~Jun-Nov) and is silent Dec-May
   — exactly the import window we care about. So DEFRA is an off-season/price
   context input; the intended in-season weekly driver is **retail-price
   scraping** (year-round supermarket prices), to be added in M2.
5. **Vintage caveat**: the live APIs serve only the *current* revision, so true
   historical vintages cannot be reconstructed — they accrue from the first pull
   forward. The store is built so that, going forward, the backtest reads each
   series exactly as it stood at decision time.

## Usage

```bash
pip install -r nowcast/requirements.txt
python3 -m nowcast.pipeline ingest          # pull all sources -> dated snapshots
python3 -m nowcast.pipeline show hmrc_blueberry_imports -n 12
pytest tests/ -q
```

Run `ingest` on a schedule to accrue the revision history M3 replays.

## Rejected alt-data methods

Real techniques that fail a hard constraint we set (see `config.REJECTED_SIGNALS`):
tasking satellites & sub-metre optical (paid), thermal reefer counting (free TIR
is 70-100 m, can't resolve ~12 m containers), freight load boards (account-gated,
ToS), container-number enumeration on Destin8/Portbase (**UK Computer Misuse Act
risk**), historical AIS (paid; target flow is road not deep-sea), Kantar (paid).
