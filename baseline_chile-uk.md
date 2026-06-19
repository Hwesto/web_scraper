# Baseline: Chile → UK fresh blueberries

The reference lane. This maps **every data point** along the Chile→UK blueberry supply
chain, what we already hold, what's free-but-unwired, and what needs a paid source —
so it doubles as the **free-information ceiling** for one lane and a **template** to
replicate across the rest of the UK supply chain and other origin→destination pairs.

**Status legend**
`✅` held & wired (free) · `🟢` free, not yet wired (extends the ceiling) ·
`💷` paid only (provider named) · `⛔` no known source at any price

> Discipline: verify reachability before wiring anything `🟢` (the standing rule).
> Every `✅`/`🟢` that accrues a dated vintage becomes back-testable; `💷`/`⛔` are the
> structural ceiling on what a free model can ever see.

---

## Stage 0 — Growing (Chilean farm)

| Data point | Status | Source | Notes |
|---|---|---|---|
| Orchard area by region / variety / planting-year | ✅ | Catastro Frutícola (CIREN-ODEPA) | block-level, ~3-yr survey rotation |
| Bearing-capacity trajectory | ✅ | derived (`capacity.py`) | planting-age × yield curve (assumption) |
| Actual yield per hectare | 💷 | CIREN paid directory / iQonsulting | not in free Catastro |
| Production cost £/kg (inputs, labour) | ⛔/💷 | industry studies (iQonsulting, ODEPA ad-hoc) | the margin gap; no free per-kg feed |
| Named grower → orchard → GGN cert | 💷 | CIREN (named); GlobalG.A.P. validate-only | no free name→GGN discovery |
| Organic vs conventional area | 💷 | certifier registries | partial hints only |
| Weather / frost / chill-hours (growing regions) | 🟢 | NASA POWER, NOAA, Meteochile | free, leading; not wired |
| NDVI greenness — **Chilean** regions | 🟢 | NASA/ORNL (we already use it for Morocco/Spain) | extend existing module |
| Drought / water-allocation index | 🟢 | Chilean DGA, NASA | free, not wired |
| Pesticide / agrochemical use | ⛔/💷 | — | not public |

## Stage 1 — Harvest & packing

| Data point | Status | Source | Notes |
|---|---|---|---|
| Packhouse hiring (labour demand, leading) | ✅(stub) | gov.uk-style job boards / agency pages | forward-only, no history |
| China-authorised orchards + packing facilities | ✅ | SAG roster | 3,966 orchards; facilities sheet too |
| Harvest progress / timing by region | ⛔ | — | proxy via exports/NDVI only |
| Packhouse throughput | ⛔ | — | proxy via hiring (weak) |
| Pack format / punnet-size split at source | ⛔ | — | not in customs |
| Grade / quality at packing | ⛔/💷 | exporter QC, third-party | not public |
| Cold-storage volumes | ⛔ | — | — |

## Stage 2 — Export (leaving Chile, origin customs)

| Data point | Status | Source | Notes |
|---|---|---|---|
| Volume Chile→UK, weekly | ✅ | Aduana DUS cargo | de-anonymised |
| FOB price Chile→UK, weekly | ✅ | DUS (declared) | USD/kg |
| Named exporter (RUT, comuna) | ✅ | DUS | — |
| Named producer / marca | ✅ | DUS | ~72 named |
| Cultivar per shipment | ✅ | DUS | declared on ~half |
| Region of origin | ✅ | DUS | — |
| Volume Chile→UK, **daily** | 🟢 | datos.gob.cl daily DUS | free but TLS-blocked from our egress — needs clean fetch |
| Port of loading | 🟢 | DUS (likely present) | not yet extracted |
| **Bill of lading: exporter → UK consignee** | 💷 | Panjiva (S&P), ImportGenius, Datamyne | links shipper to the UK importer — the key identity join |
| Vessel / shipping line / container count | 💷 | the same BoL providers; AIS | — |
| Phyto certificate per consignment | ⛔ | SAG per-consignment (not bulk) | — |

## Stage 3 — Shipping & transit

| Data point | Status | Source | Notes |
|---|---|---|---|
| Transit time Chile→UK (~26–32 d) | ✅ | assumption / model | drives the nowcast shift |
| In-transit (afloat) volume | ✅ | derived (transit-shift) | — |
| Reefer freight rate Chile→UK | ✅(assumed) | reefer-rate ÷ payload (documented) | real rates are 💷 Xeneta / Freightos FBX / Drewry |
| Vessel position / ETA (AIS) | 🟢/💷 | AISStream/free tiers; MarineTraffic/Spire (paid) | free tiers are rate-limited |
| Port congestion / dwell | 🟢 | some port-authority feeds | patchy free |
| Cold-chain temperature integrity | ⛔/💷 | carrier reefer telemetry | not public |

## Stage 4 — UK arrival (HMRC border)

| Data point | Status | Source | Notes |
|---|---|---|---|
| UK import volume from Chile, monthly | ✅ | HMRC OTS (CN8 08104050) | the anchor, ~6-wk lag |
| UK import value → CIF £/kg from Chile | ✅ | HMRC OTS | derived unit value |
| **Fresh vs frozen** split | 🟢 | HMRC frozen CN code (0811…) | not yet pulled |
| Port of entry | 🟢/💷 | HMRC RTS (partial); BoL (paid) | — |
| **UK importer identity (consignee)** | 💷 | Panjiva / ImportGenius / Datamyne | the wholesale-link join |
| UK import **weekly/daily** | ⛔ | — | HMRC is monthly; no free sub-monthly UK customs |
| Volume by variety / organic at border | ⛔ | — | single CN code, type-blind |
| Phyto interceptions / rejections at UK border | 🟢 | APHA / PHSI plant-health publications | free-ish, verify |

## Stage 5 — UK wholesale / distribution

| Data point | Status | Source | Notes |
|---|---|---|---|
| Wholesale price £/kg | ✅(partial) | DEFRA (Jun–Nov only) | silent Dec–May (the Chile window) |
| Wholesale price, year-round | 🟢/💷 | New Covent Garden (request-only) | semi-free |
| **Importer → retailer price** | ⛔/💷 | trade contacts; no public feed | the biggest single gap |
| Importer margin | ⛔ | — | derived/estimated only |
| Wastage / shrink rates | ⛔/💷 | Kantar / WRAP | — |
| UK-side logistics cost | ⛔ | — | — |

## Stage 6 — UK retail (shelf)

| Data point | Status | Source | Notes |
|---|---|---|---|
| Retail shelf price £/kg, multi-retailer | ✅ | Trolley (live) | weekly, forward |
| Retail price by retailer × tier × pack-size | ✅ | Trolley | standard/organic/finest, 125–500 g |
| Retail price history (year-round) | ✅ | ONS (2018→2025 + all-berry proxy) | monthly |
| ONS grocery **scanner** data (~50% of market) | 🟢 | ONS | official roll-in from 2026 |
| Promotions / discount depth | 🟢 | own scrape; Assosia (paid) | flags scrapeable |
| Own-brand vs branded | 🟢 | Trolley flag / Kaggle (abandoned) | partial |
| Country of origin **on shelf** | ⛔ | — | rotates weekly, unlabelled online |
| Variety **on shelf** | ⛔ | — | never labelled in retail |
| **Units sold / sales value** | 💷 | Kantar, NielsenIQ, Circana (IRI) | the demand quantity |
| Retailer market share | 💷 | Kantar | — |

## Stage 7 — Consumer / demand

| Data point | Status | Source | Notes |
|---|---|---|---|
| Search interest (Google Trends) | 🟢 | Google Trends | free, leading-ish |
| Household consumption / penetration | 🟢/💷 | DEFRA Family Food (free, lagged); Kantar (paid) | — |
| Price elasticity | ⛔ | derived | — |
| Reviews / sentiment | 🟢 | retailer review scrape | noisy |

## Cross-cutting

| Data point | Status | Source | Notes |
|---|---|---|---|
| FX USD/GBP/CLP | 🟢 | Bank of England / ECB | we use a notional rate; real is free |
| Tariffs / duties Chile→UK | 🟢 | UK Trade Tariff (UK-Chile agreement) | fresh blueberries 0% — confirm & note |
| Competing-origin timing (Peru/Morocco/SA) | ✅ | HMRC origin mix | the relay |
| Production / export **forecasts** | 🟢/💷 | USDA FAS (free); iQonsulting, Frutas de Chile (paid/partial) | season-ahead |
| US tariff context (re-routes Chile allocation) | 🟢 | USTR / USDA | free |

---

## The free ceiling vs the paid layer

**Free baseline (✅ + 🟢) reaches:** the whole *physical-flow and price* spine — grow →
ship → border → shelf — at origin and destination, plus weather/NDVI/forecast leading
signals. That is enough to model and **back-test** volume and landed price end-to-end.

**Paid unlocks three things free data structurally can't:**
1. **Identity join shipper↔importer** (bill-of-lading: Panjiva / ImportGenius / Datamyne)
   — who actually buys from whom.
2. **Demand quantity** (Kantar / NielsenIQ / Circana) — units sold, share, penetration.
3. **Real freight & farm cost** (Xeneta/Freightos; CIREN/iQonsulting) — to replace our
   documented assumptions with measurements.

**Structural `⛔` (no source, free or paid):** shelf-level origin/variety attribution,
sub-monthly UK customs, harvest-progress telemetry — these are not collected anywhere.

## How to replicate (the template)

1. Copy this file → `baseline_<origin>-<dest>.md`; keep the 8 stages + cross-cutting.
2. Swap the origin-customs row-set (Stage 2) for that country's feed (e.g. Peru SUNAT/
   Agrodata, China GACC) and the destination-customs rows (Stage 4) for that market.
3. Stages 0/1/5/6/7 and cross-cutting are **largely lane-independent** — they get easier
   each time (HMRC, Trolley, ONS, freight, FX, forecasts all carry over for UK-import
   lanes; only origin-side customs and orchard structure change).
4. Each `🟢` you wire starts a dated vintage → another back-testable series.
