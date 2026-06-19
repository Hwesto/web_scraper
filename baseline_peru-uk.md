# Baseline: Peru → UK fresh blueberries

Second lane, filled against the Chile template. Peru is now the **world's #1 blueberry
exporter** (~360 k t/season), so the flow/price side is rich — but it has **no orchard
census like Chile's Catastro**, so the structural/capacity layer can't be replicated.
"Determine all that can be filled" = the `🟢` rows below (verified where noted).

`✅` held/wired · `🟢` free, fillable (not yet wired) · `💷` paid · `⛔` no source ·
*lane-independent* rows carry over from Chile unchanged.

---

## Stage 0 — Growing (Peruvian farm)

| Data point | Status | Source / note |
|---|---|---|
| Orchard area by **region** | 🟢 | MIDAGRI / USDA-FAS / committee reports — **regional aggregates only** (2023: ~18.6 k ha; La Libertad 8.4 k / 45 %, Lambayeque 5.4 k / 29 %, then Ica/Lima/Ancash/Piura/Moquegua/Cajamarca) |
| **Per-block variety × planting-year census** | ⛔ | **No Peruvian equivalent of Chile's Catastro.** → the capacity-trajectory model and the variety-renewal block **cannot be built for Peru** (the key asymmetry) |
| Variety mix | 🟡/⛔ | qualitative from reports (Biloxi, Ventura, proprietary Sekoya/Rocío) — not a structured feed |
| Production cost £/kg | ⛔/💷 | farmdoc / USDA studies (Peru cost rising with labour) |
| Weather / NDVI (growing regions) | 🟢 | free (NASA/Sentinel) — but Peru is irrigated coastal desert, so NDVI is less crop-diagnostic; satellite parked anyway |

## Stage 1 — Harvest & packing

| Data point | Status | Source / note |
|---|---|---|
| **Season export progress, by week** | 🟢 | **ProArándanos** publishes weekly campaign volumes (peak week, cumulative) — Peru's analogue of Chile's DUS weekly, and arguably *better* season data. Site reachable (200); confirm raw/structured access vs press-republished (Agronometrics/FreshFruitPortal) |
| Packhouse hiring (leading) | 🟢 | same concept as Chile (forward-only) |
| Grade / pack format | ⛔ | not public |

## Stage 2 — Export (leaving Peru, origin customs)

| Data point | Status | Source / note |
|---|---|---|
| Export FOB Peru→UK | ✅ | Comtrade ($6.65/kg, 16.2 k t, 2024) — held in `origin_export_prices` |
| Export volume/price Peru→**all destinations** | 🟢 **verified** | Comtrade reporter=Peru — **US 180 k t @ $6.80, Netherlands 72 k t, Hong Kong 26 k, UK 16 k, China 14 k** (2024). → a **Peru netback** ("where does Peru sell") is free, mirror of `comtrade.py` |
| Volume Peru→UK, weekly/seasonal | 🟢 | ProArándanos / SUNAT — verify raw access (vs Chile, where we have DUS) |
| Named exporter | 🟢/💷 | Agrodata / SUNAT (partly free) — Camposol, Hortifrut Perú, Agrovisión, Danper… |
| **Cultivar per shipment** | ⛔ | SUNAT customs doesn't carry cultivar the way Chile's DUS does |
| Bill of lading → UK consignee, vessel | 💷 | Panjiva / ImportGenius / Datamyne |

## Stage 3 — Shipping & transit *(lane-adjusted)*

| Data point | Status | Source / note |
|---|---|---|
| Transit Peru→UK (~3–4 wk, ex-Callao/Paita) | ✅ | shorter than Chile; freight model carries over |
| Reefer freight rate | ✅(assumed)/💷 | our reefer÷payload assumption; real = Xeneta/Freightos |
| AIS vessel position | 🟢/💷 | free tiers / MarineTraffic |

## Stage 4 — UK arrival (HMRC border)

| Data point | Status | Source / note |
|---|---|---|
| UK import volume from Peru, monthly | ✅ | HMRC OTS (held; Peru is a top-3 UK origin) |
| UK CIF £/kg from Peru | ✅ | HMRC unit value (held; ~£5–6.8/kg seasonal) |
| Peru→UK **dashboard block** | ✅ | seasonality + FOB→CIF wedge, already live |
| Fresh vs frozen / port / importer | 🟢 / 💷 | frozen CN code (free); consignee (paid) — *same as Chile* |

## Stages 5–7 — Wholesale · Retail · Consumer *(lane-independent — carry over)*

| Data point | Status | Source |
|---|---|---|
| UK wholesale £/kg | ✅(partial) | DEFRA (Jun–Nov) |
| Importer→retailer price; margins | ⛔/💷 | — |
| Retail shelf £/kg (multi-retailer) | ✅ | Trolley + ONS — *origin-blind anyway* |
| Units sold / share / consumption | 💷/🟢 | Kantar·NielsenIQ·Circana (paid); DEFRA Family Food (free) |

## Cross-cutting

| Data point | Status | Source |
|---|---|---|
| USD/GBP FX | ✅ | ECB (fx.py) — held |
| Tariff Peru→UK | 🟢 | UK-Andean agreement — fresh blueberries 0 %; confirm & note |
| **Season forecasts** | 🟢 **verified** | **USDA FAS "Blueberry Annual – Lima"** (free PDF, 200) + ProArándanos estimates — Peru has *stronger* forward data than Chile |
| Competing-origin timing | ✅ | HMRC origin mix (the relay) |
| Phyto access (Peru→China / →US) | 🟢 | GACC-registered Peruvian orchards / APHIS — analogue of the SAG-China roster |

---

## Verdict — what can be filled

**Easier than Chile (flow & price):**
1. **Peru netback** (Comtrade reporter=Peru) — *verified*, a ~1-day mirror of `comtrade.py`. Top immediate win.
2. **ProArándanos weekly season volumes** — the rich origin feed (verify structured access).
3. **USDA-FAS + ProArándanos forecasts** — *verified free*; Peru's forward data beats Chile's.
4. **MIDAGRI regional hectares** — coarse area (region, not block).
5. **Peru→China GACC phyto roster** — same trick as SAG.

**Already held:** HMRC Peru→UK volume+CIF, Comtrade Peru→UK FOB, the Peru→UK block, and
every lane-independent layer (Trolley, ONS, FX, freight, importer side).

**Cannot be filled free (the asymmetry):**
- **No per-block orchard census** → no capacity-trajectory model, no variety-renewal block.
  Peru's structure is regional aggregates + corporate estates, not a Catastro.
- **No cultivar-per-shipment** (SUNAT ≠ Chile DUS) → no shipped-variety mix.
- Importer identity, demand quantity → paid (same as Chile).

**Recommended build order:** Peru netback (verified, cheap) → ProArándanos weekly (if
access confirmed) → forecasts. Skip the structural layer — it isn't there to get.
