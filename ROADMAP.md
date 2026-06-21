# ROADMAP — plugging every gap

A full, prioritised plan to close every gap surfaced in the data audit. Pairs with
`FRONTIER_SOURCES.md` (what's available per source) and the registry (the structured map).

**How to read:** tiers run **P0 (do now — cheap + high value)** → **P5 (depth / nice-to-have)**.
Each item: _gap · why it matters · approach · effort · status_. Status legend: ✅ done ·
🔑 built-needs-key · 🔧 partial · ⬜ not started.

Current state (2026-06): registry **40 held · 49 base-covered · 27 headroom · 18 info-only ·
20 paid · 25 structural-gap**. The global reconciliation accounts for ~90% of every major
origin's exports, backtested (mirror 1.10). The production layer is corrected (China #1).

---

## P0 — Activate what's already built (hours, no new code)
| # | Gap | Approach | Status |
|---|---|---|---|
| 0.1 | **US imports not live** (Comtrade-lagged) | set `CENSUS_API_KEY` → `atlas/uscensus.py` pulls current monthly US imports by origin; `global_reconcile` auto-switches | 🔑 built |
| 0.2 | **US weekly movement stale** (keyless to early-2025) | set `AMS_API_KEY` → `atlas/usda_movement.py` MARS API (slug 3251), live weekly | 🔑 built |
| 0.3 | ~~Scatter reads raw FAOSTAT (no China)~~ | China added (810kt grown / $23M exported, annotated) | ✅ done |
| 0.4 | **Reconciliation/bloc breakdown not surfaced** | add a "where each origin's exports go" panel (EU/US/Asia/UK/residual) to the dashboard | ⬜ small |
| 0.5 | **USDA-NASS current US production** | needs free `NASS_API_KEY` (401) — build the fetcher behind it | 🔑 not built |

## P1 — Production layer completion (high value)
| # | Gap | Approach | Status |
|---|---|---|---|
| 1.1 | FAOSTAT-missing producers: China, S.Africa, Argentina | snapshots merged via `production.top_global()` | ✅ done |
| 1.2 | Remaining FAOSTAT-missing: **Uruguay, Serbia, Georgia, Belarus** (smaller) | add to `production.csv` (IBO / national) | ⬜ low effort |
| 1.3 | **Current-year production** (FAOSTAT lags ~2yr) — only Peru/Mexico/China are current | USDA-NASS needs a key (🔑); StatCan WDS keyless but complex coord-system for marginal gain; add committee current (Chile/Spain-Huelva/Morocco) to `production.csv` | 🔧 partial |
| 1.4 | **Area/yield** for snapshot producers (China/Yunnan, SA, Argentina) | extend `production.csv` (have China total/Yunnan-area, SA area) | 🔧 partial |
| 1.5 | China production as a **time series** (only 2020 & 2025 points) | back-fill 2021-24 from press/GACC | ⬜ |

## P2 — Trade currency completion (close the residual)
| # | Gap | Approach | Status |
|---|---|---|---|
| 2.1 | **EU** bilateral live | Eurostat monthly to 2026-04 | ✅ done |
| 2.2 | **UK** by-origin only Comtrade-lagged | wire **HMRC OTS** by-origin (free; partly in nowcast) — fresher UK slice | 🔧 |
| 2.3 | **Canada** import slice Comtrade-only | **StatCan WDS** free API, imports by origin | ⬜ |
| 2.4 | Small importers (Norway, Switzerland, Gulf, Russia) | national customs / leave to Comtrade residual | ⬜ low priority |
| 2.5 | **China current bilateral** | GACC JS-anti-bot gated → keep press snapshot (`atlas/china.py`); paid resellers only for live | ✅ snapshot (hard limit) |

## P3 — Forecast & the divergence tracker
| # | Gap | Approach | Status |
|---|---|---|---|
| 3.1 | ~~Forecast-vs-actual tracker~~ | `atlas/divergence.py` -> divergence.csv: flags BEAT/MISS/REVERSAL/SURPRISE (caught Peru +14% vs GAIN, Chile +31pp, Morocco reversal, Peru->China +153%) | ✅ done |
| 3.2 | Forecasts only Peru+Mexico (GAIN) | add GAIN reports for Chile/S.Africa where they exist; treat committee `yoy_growth` as forecasts | 🔧 |
| 3.3 | No structured **projection vs realised** per season | per-season committee projection vs final | ⬜ |

## P4 — Condition, demand & entity depth
| # | Gap | Approach | Status |
|---|---|---|---|
| 4.1 | NASA POWER only 14 regions; missing **Yunnan, more SA/Argentina/Australia** | add growing regions to `nasa_power.REGIONS` | ⬜ |
| 4.2 | **China price collapse** captured as one snapshot, not a series | track premium farm-gate ¥/kg over time | ⬜ |
| 4.3 | Demand/retail thin (UK deep via Trolley/ONS; **US/EU/China retail unwired**) | USDA-AMS retail (US); EU/China are paid/scrape | ⬜ |
| 4.4 | Named-exporter depth: Peru ✅; **Chile DUS RUT-anonymised** | map RUT→company; other origins paid | 🔧 |
| 4.5 | NDVI / drought (Chile catalogued, unwired) | satellite indices | ⬜ |

## P5 — Breadth, quality, surfacing
| # | Gap | Approach | Status |
|---|---|---|---|
| 5.1 | **Multi-fruit** proven (avocado) but not populated | run overlays for a 2nd fruit (cherry/avocado) — `commodity=` param | 🔧 proven |
| 5.2 | Data-quality flags: **Chile mirror gap ~24%**, **Mexico export<US-import anomaly** | surface as confidence badges in reconciliation | ⬜ |
| 5.3 | 27 "true headroom" free-unwired points (fragile demand/origin detail) | wire selectively; most are low-value/fragile | ⬜ |
| 5.4 | **Dashboard** doesn't yet show reconciliation, forecast-vs-actual, China dossier, corrected production | full surfacing pass (`PRODUCT_SPEC.md`) | ⬜ |
| 5.5 | **Data-export JSON** layer (`docs/data/atlas.json`) | decouple data from render | ⬜ |
| 5.6 | Open the **PR** / GitHub Pages live | merge `claude/phase-0-1-setup-0bb0sx` | ⬜ |

---

## The genuine hard limits (not closeable for free)
- **China current bilateral** — GACC JS-anti-bot gated; only Comtrade-lagged + press snapshot.
- **Named exporter / bill-of-lading** granularity — paid (Agronometrics/Agrodata/Tridge).
- **Live US/AMS at full granularity** — needs the free keys (P0.1/0.2), else lagged.
- Everything else above is reachable with free sources.

## Suggested sequence
**P0 first** (activate keys + 2 dashboard fixes — a day) → **P3.1 the divergence tracker**
(highest analytical value) → **P1.3 current production** (NASS/StatCan free APIs) → **P2.2/2.3
UK+Canada slices** → **P5.4 surfacing**. The rest is depth.
