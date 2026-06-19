# Data sources — master link list

Every feed behind the project, with its live endpoint, what it gives, time depth, and
status. `LIVE` wired & refreshing · `DERIVED` computed from another feed · `PROXY`
documented stand-in · `PROBE` validated, not yet a pipeline · `STUB` schema only ·
`CANDIDATE`/`PAID` not wired. Each dashboard block is stamped with the source(s) below.

> Combined **data-point × link × renewal** reference: see **`DATA.md`**.

---

## Flow & volume

| Source | Link | Gives | Depth | Status · module |
|---|---|---|---|---|
| **HMRC OTS** | `api.uktradeinfo.com` (OData) | UK imports by origin — mass + customs value, CN8 08104050 | **2018→now**, monthly, ~6wk lag | `LIVE` · `data/hmrc.py` |
| **Chile Aduana DUS** | `datos.gob.cl` (CKAN) | Chile→UK shipments: named exporter/producer + cultivar + region | **2018→now**, weekly | `LIVE` (cron, clean egress) · `scripts/fetch_chile_weekly_exports.py` |
| **ODEPA** | `datos.gob.cl` (CKAN) | Chile→UK export tonnes (official mirror / cross-check) | monthly | `LIVE` · `volume/data/odepa_chile.py` |
| Fused UK supply | — | year-round all-origin UK supply | weekly | `DERIVED` · `volume/uk_total.py` |

## Prices

| Source | Link | Gives | Depth | Status · module |
|---|---|---|---|---|
| **HMRC unit value** | (from HMRC OTS) | UK-landed **CIF £/kg by origin** (~46 origins) | 2018→now, monthly | `DERIVED` · `price.py` |
| **UN Comtrade — destinations** | `comtradeapi.un.org` (preview) | what each market pays Chile **&** Peru (CIF $/kg, by partner) | **2012→2025** | `LIVE` · `market/comtrade.py` |
| **UN Comtrade — origin export** | `comtradeapi.un.org` | every origin's export FOB $/kg (World + UK) → the FOB→CIF wedge | **2012→2025** | `LIVE` · `market/origin_prices.py` |
| **DEFRA wholesale** | `gov.uk/.../statistical-data-sets` | UK wholesale £/kg | 2018→now, weekly, **Jun–Nov only** | `LIVE` · `data/defra_price.py` |
| **ONS retail** | `ons.gov.uk/file` (pre-2025) + `github.com/onsdigital/cpi-items-actions` (post) | UK retail £/kg, year-round | **2018→2026** (proxy after Jan-25) | `LIVE`+`PROXY` · `data/ons_price.py` |
| **Trolley (retail shelf)** | `trolley.co.uk/product` | multi-retailer shelf £/kg by retailer × tier × pack | forward (weekly) | `LIVE` · `data/retail_price.py` |
| **FX USD→GBP** | `api.frankfurter.app` (ECB) | real reference rate (replaces notional 0.79) | daily | `LIVE` · `market/fx.py` |

## Structure, forward & access

| Source | Link | Gives | Depth | Status · module |
|---|---|---|---|---|
| **Catastro Frutícola** | `datos.odepa.gob.cl` | Chile orchard area × variety × planting-year → capacity + renewal | **1987→2024** | `LIVE` · `farm/data/catastro.py` → `capacity.py` |
| **USDA-FAS Blueberry Annual** | `apps.fas.usda.gov/newgainapi` | **Peru** area/production/exports/exports-to-US + 2-season forecast | 2022/23→2026/27 | `LIVE` (annual) · `scripts/fetch_usda_peru.py` |
| **SAG China roster** | `sag.gob.cl/.../exportaciones/registros` (xlsx) | 3,966 China-authorised Chilean orchards | season | `LIVE` · `scripts/fetch_sag_china.py` |
| **GlobalG.A.P. / GGN** | `ggn.org/search.html` | cert validate / enrich (no name→GGN discovery) | — | `DERIVED` · `farm/certs.py` |

## Leading / experimental (satellite & alt-data)

| Source | Link | Gives | Status · module |
|---|---|---|---|
| **Sentinel-2 (Tier 2)** | `earth-search.aws.element84.com` + `sentinel-cogs` S3 | 10 m crop-condition NDVI over blueberry comunas | `PROBE` — cautious GO, not pipelined · `scripts/sentinel_probe.py` |
| **MODIS NDVI** | `modis.ornl.gov/rst` | 250 m regional greenness (Spain/Morocco; Chile coded) | `LIVE` (throttle-flaky) · `data/ndvi.py` |
| **Packhouse hiring** | (job boards) | temp-role postings as a leading wave signal | `STUB` · `data/altdata/job_boards.py` |

---

## Candidates & paid (not wired)

| Source | Would add | Status |
|---|---|---|
| **ONS grocery scanner data** | ~50% of UK retail, official | 🟢 free, rolls in **2026** |
| **Eurostat COMEXT** | EU import/export prices (Spain/NL/Poland detail) | 🟢 free |
| **Peru→China GACC roster** | Peru phyto access (SAG analogue) | 🟢 if list fetchable |
| **ProArándanos weekly** | Peru weekly campaign volumes | ⚠️ **no structured feed** — 403/press-only |
| Bill of lading — **Panjiva · ImportGenius · Datamyne** | shipper↔UK-importer identity, vessel | 💷 |
| Retail sales — **Kantar · NielsenIQ · Circana** | units sold, share, consumption | 💷 |
| Real freight — **Xeneta · Freightos · Drewry** | measured reefer rates (replace assumption) | 💷 |
| Orchard registry — **CIREN** (Chile) / SUNAT-Agrodata (Peru) | named/yield detail | 💷 |

## Structural gaps (no source, free or paid)

Shelf-level origin/variety attribution · sub-monthly UK customs · importer→retailer
price & margins · per-block orchard census for Peru · cultivar-per-shipment for Peru.

---

## At a glance

- **Time depth is now uniform** — every core layer runs 2018→present (Comtrade 2012,
  Catastro 1987). No more snapshot caches.
- **Two origins covered:** Chile (deep — flow, named producers, varieties, capacity,
  renewal, phyto) and Peru (flow, netback, USDA forward outlook).
- **Lane-independent layers** (HMRC, Trolley, ONS, FX, freight, Comtrade origin prices)
  carry to any new UK-import lane — only origin customs + orchard structure change.
- See `baseline_chile-uk.md` / `baseline_peru-uk.md` for the per-lane gap maps.
