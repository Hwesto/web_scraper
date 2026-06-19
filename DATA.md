# DATA — blueberry data points × links × renewal

The combined reference: every blueberry **data point** we hold, its **source link**, time
**depth**, **renewal cadence (ours = how often we refresh · theirs = how often the source
publishes)**, and status. (Source-only catalogue: `SOURCES.md`; per-lane gaps:
`baseline_*.md`.)

Status: `LIVE` wired · `DERIVED` computed · `PROXY` stand-in · `PROBE` validated only ·
`STUB` schema only.

---

## A. Volume & flow

| Data point | Source · link | Depth | Ours | Theirs | Status |
|---|---|---|---|---|---|
| UK imports by origin (tonnes) | HMRC OTS · `api.uktradeinfo.com` | 2018→now | **manual** (`pipeline ingest`) | monthly (~6wk lag) | LIVE |
| UK import value by origin (£) | HMRC OTS · `api.uktradeinfo.com` | 2018→now | **manual** | monthly | LIVE |
| Chile→UK volume (net kg) | Chile DUS · `datos.gob.cl` | 2018→now | weekly-cron | ~daily | LIVE |
| Chile→UK named producer / exporter / cultivar / region | Chile DUS · `datos.gob.cl` | season | weekly-cron | ~daily | LIVE |
| Chile→UK volume (official mirror) | ODEPA · `datos.gob.cl` | monthly | manual | periodic | LIVE |
| Fused all-origin UK supply (weekly) | — derived | 2018→now | weekly-cron | — | DERIVED |

## B. Prices

| Data point | Source · link | Depth | Ours | Theirs | Status |
|---|---|---|---|---|---|
| UK-landed **CIF £/kg by origin** (~46) | HMRC (value÷vol) | 2018→now | manual | monthly | DERIVED |
| Chile **FOB $/kg** weekly | Chile DUS · `datos.gob.cl` | 2018→now | weekly-cron | ~daily | LIVE |
| Chile **&** Peru **CIF $/kg by destination** | UN Comtrade · `comtradeapi.un.org` | **2012→2025** | weekly-cron (rolling) | annual (revised) | LIVE |
| Every origin **export FOB $/kg** (World+UK) → wedge | UN Comtrade · `comtradeapi.un.org` | **2012→2025** | weekly-cron | annual | LIVE |
| UK **wholesale £/kg** | DEFRA · `gov.uk/.../statistical-data-sets` | 2018→now (Jun–Nov) | manual | weekly→fortnightly | LIVE |
| UK **retail £/kg** (monthly, +proxy) | ONS · `ons.gov.uk` + `github.com/onsdigital/cpi-items-actions` | 2018→2026 | weekly-cron | monthly | LIVE+PROXY |
| UK **retail shelf £/kg** by retailer×tier×pack | Trolley · `trolley.co.uk/product` | forward | weekly-cron | ~daily | LIVE |
| **FX USD→GBP** | Frankfurter/ECB · `api.frankfurter.app` | daily | weekly-cron | daily | LIVE |

## C. Structure, forward & access

| Data point | Source · link | Depth | Ours | Theirs | Status |
|---|---|---|---|---|---|
| Chile orchard **area × variety × planting-year** | Catastro · `datos.odepa.gob.cl` | **1987→2024** | manual snapshot | ~3-yr rotation | LIVE |
| Peru **area / production / exports / exports-to-US + forecast** | USDA-FAS · `apps.fas.usda.gov` | 2022/23→2026/27 | **manual (annual)** | annual (~Jun) | LIVE |
| China-authorised Chilean orchards (3,966) | SAG · `sag.gob.cl/.../registros` | season | weekly-cron | seasonal | LIVE |
| Cert status / GGN validate | GlobalG.A.P. · `ggn.org/search.html` | — | on-demand | continuous | DERIVED |

## D. Leading / experimental

| Data point | Source · link | Ours | Theirs | Status |
|---|---|---|---|---|
| Sentinel-2 10 m crop NDVI (blueberry comunas) | `earth-search.aws.element84.com` + `sentinel-cogs` S3 | probe-only | ~5-day revisit | PROBE |
| MODIS 250 m regional NDVI | `modis.ornl.gov/rst` | manual (parked) | 16-day | LIVE (flaky) |
| Packhouse hiring counts | job boards | forward (not built) | continuous | STUB |

## E. Derived (computed from the above — no external link)

| Data point | Built from | Status |
|---|---|---|
| **Netback $/kg by destination** (Chile, Peru) | Comtrade CIF − freight | DERIVED |
| **FOB→CIF freight wedge** per origin | Comtrade FOB vs HMRC CIF | DERIVED |
| **Asia premium $/kg**; China-approved producer coverage % | Comtrade + SAG | DERIVED |
| **Bearing-capacity trajectory**; **variety-renewal** (Chile) | Catastro × yield curve | DERIVED |
| **Nowcast**: Chilean arrivals ~2 wks early, direction-skill | HMRC + DUS model | DERIVED |

---

## Renewal: ours vs theirs — where they diverge

- **HMRC (the anchor) refreshes *manually*, not on the weekly cron** — same for DEFRA,
  ODEPA, NDVI. Worth fixing: add `pipeline ingest` to the workflow so the ground-truth
  series stays as current as the rest.
- **Comtrade**: we re-pull weekly but it only publishes annually — harmless (the rolling
  refresh just re-reads recent years), the deep history is backfilled once and merged.
- **Trolley / Chile-DUS / FX**: source updates daily, we sample weekly — adequate; only
  the Trolley shelf series is forward-only (no history).
- **Catastro / USDA**: slow upstream (3-yr / annual), so manual refresh is fine — just
  bump USDA's `REPORT_URL` when the new annual lands.

## Coverage in one line

Uniform **2018→present** depth on every core series (Comtrade 2012, Catastro 1987);
two origins (**Chile** deep, **Peru** flow+forward); lane-independent layers (HMRC,
Trolley, ONS, FX, Comtrade origin prices) ready to extend to any new UK-import origin.
