# FRONTIER — what blueberry data we measure NOW, and will measure AFTER maxing 1–3

The reasoning behind the phase order, the definition of "complete", and the full
inventory of every **measured data point** — current vs. after. Pairs with
`PHASES.md` (the checklist) and `DATA.md` (the wired-series reference). Counts are
derived from `data/atlas/registry.csv` (142 rows): **24 measured now · 74 free
but not yet wired · 13 paid-only · 16 structural gaps**.

---

## 1. Priority order across the three phases — the reasoning

The phases do **not** measure the same things, so "max all three" has a forced
order set by *coverage-per-unit-effort* and *dependency*:

- **Phase 1 = the FLOW+PRICE matrix from ONE source (UN Comtrade).** Two measured
  quantities — volume and realised unit-value — across *every exporter × importer ×
  period* cell, plus the global exporter/importer ranking. The cheapest breadth that
  exists: a single keyless API populates every lane at once. **Do first, finish first.**
- **Phase 2 = measures NOTHING.** It is the *map* (free | paid | none per country ×
  data-point). Its only job is to tell Phase 3 where digging pays. Cheap, and a
  prerequisite. **Second.**
- **Phase 3 = the OVERLAYS Comtrade is blind to:** structure (orchard area/variety),
  identity (named orchards/exporters), forward (forecasts), condition (NDVI/weather),
  access (phyto rosters/interceptions), demand (retail/consumption). Expensive,
  per-source, narrow. **Third, and selective.**

**The crucial within-Phase-3 priority.** A national customs portal (Spain DataComex,
US Census, Japan e-Stat, …) mostly *re-measures the flow Comtrade already has* — it
adds only sub-national origin region, finer national tariff codes, and timeliness.
That is **low marginal value**. The **high**-value Phase-3 wirings are the non-flow
axes Comtrade cannot see: **orchard/area census · phyto rosters · forecasts · NDVI/
weather · interceptions · retail/demand.** Wire those first; treat the ~16 national
customs portals as last-mile granularity (or skip where Comtrade+COMEXT suffice).

> **Order:** finish **P1** → complete the **P2** map → wire **P3 new-axis-first**
> (overlays before customs portals). Then **P4** = swap the HS code and re-run.

Why this beats doing them "evenly": Phase 1 already measures the spine for *all*
lanes; spending Phase-3 effort to re-measure flow per-country before the unique
overlays would buy granularity we mostly don't need while leaving whole measurement
axes (structure, forward, demand) empty.

---

## 2. What "complete" looks like

**Complete (the maximum of *free*)** = every data point that has a free, reachable,
**parseable** source is **wired and refreshing**; every target-set country × category
carries an explicit verdict; and the *only* things left unmeasured are the
**paid ceiling** (§4) and the **structural gaps** (§5) — both mapped, not guessed.

Concretely: measured series grow from **24 → ~98** instances. The boundary of the
free model is then fully drawn — we know exactly what costs money (13 data-point
types) and what is collected nowhere at any price (16 types). Phase 4 re-runs this
entire machine for the next fruit (HS code is a parameter).

Per-phase "done":
- **P1 done** — ranking + bilateral (annual, full history 2012→present) + monthly
  seasonality + EU COMEXT, both flows, with a per-year coverage/quality table and
  a complete HS join key (HS6 + national splits + frozen 0811.90 / dried 0813.40).
- **P2 done** — every country in the 95→99% set, both roles, all five overlay
  categories filled with a verdict; every source URL probed (verified or flagged).
- **P3 done** — every free, parseable overlay wired (new-axis-first); nothing free
  left merely catalogued.

---

## 3. Measured data points — CURRENT (24) → AFTER (~98), by supply-chain stage

`[NOW]` = wired & refreshing today · `[AFTER]` = free + parseable, wires when maxed.
Flow/price (Stage 2/4) is largely **global already** via Comtrade; the AFTER growth
is concentrated in the overlays (Stage 0, 4-phyto, 6–7, forecasts).

### Stage 0 — Growing (farm structure & condition)
- **Area / production / yield by country** — `[NOW]` **global, all countries**
  (FAOSTAT, `atlas/faostat.py`) — the production base layer (FAO is to growing what
  Comtrade is to trade). FAO area includes wild lowbush for US/CA.
- Orchard **area by region/variety/planting-year** (finer than FAO national totals) —
  `[NOW]` Chile (Catastro, block-level) · `[AFTER]` overlays: Spain (ESYRCE, plot-level),
  USA (NASS), Mexico (SIAP), Canada (StatCan), Poland (GUS), Netherlands (CBS),
  South Africa (Berries ZA), Morocco, Germany, Portugal, South Korea, Serbia, France
- **Bearing-capacity trajectory** (derived) — `[NOW]` Chile · `[AFTER]` only where a
  block-level planting-year census exists (Chile; partially Spain)
- **Variety-renewal trajectory** (derived) — `[NOW]` Chile
- **NDVI / crop condition** — `[AFTER]` Chile (probe→wire), extensible to any region
- **Weather / frost / chill-hours** — `[AFTER]` Chile (NASA POWER — globally extensible)
- **Drought / water-allocation index** — `[AFTER]` Chile (DGA)
- **Named authorised export orchards (phyto roster)** — `[NOW]` Chile (SAG-China),
  Mexico (SENASICA) · `[AFTER]` Morocco (ONSSA), South Africa (PUC/PHC), Peru (GACC),
  China (CIFER, registered overseas producers), Portugal (DGAV), Serbia, Belgium

### Stage 1 — Harvest & packing
- **Packhouse hiring** (leading) — `[AFTER]` Chile/global (job boards; forward-only)
- *(harvest progress, packhouse throughput, pack format — structural gap, §5)*

### Stage 2 — Export (origin customs)
- **Volume by origin→destination** — `[NOW]` global (Comtrade matrix, annual+monthly,
  exporter target set) + Chile weekly (DUS) · `[AFTER]` national-customs sub-national
  detail for 16 origins; Peru weekly (ProArándanos, fragile); Chile daily
- **Realised export price $/kg by destination** — `[NOW]` global (Comtrade matrix);
  EU EUR/kg (COMEXT) · `[AFTER]` finer national unit values
- **Named exporter** — `[NOW]` Chile (DUS) · `[AFTER]` Peru (Agrodata/SUNAT, partial)
- **Cultivar per shipment** — `[NOW]` Chile (DUS) *(structural gap elsewhere)*
- **Region of origin** — `[NOW]` Chile · `[AFTER]` Spain (province), USA (state), etc.
- **Port of loading** — `[AFTER]` Chile (DUS field, not yet extracted)
- **Season export progress, weekly** — `[AFTER]` Peru (ProArándanos, fragile scrape)

### Stage 3 — Shipping & transit
- **Transit time / afloat volume** (derived) — `[NOW]` Chile, Peru
- *(reefer freight, AIS, congestion — paid/§4 or thin-free)*

### Stage 4 — Border (import customs)
- **Import volume by origin** — `[NOW]` UK (HMRC) · `[AFTER]` every major importer:
  EU members (COMEXT, wired), USA, Canada, China, Japan, South Korea, Switzerland
- **Import CIF £/€/kg by origin** — `[NOW]` UK (HMRC, derived); EU (COMEXT) · `[AFTER]`
  remaining importers via national customs
- **Fresh vs frozen split** — `[AFTER]` UK (HMRC frozen CN 0811…)
- **Re-export split** — `[AFTER]` Hong Kong (the only clean one), Netherlands (CBS)
- **Port of entry** — `[AFTER]` UK (HMRC RTS, partial)
- **Phyto import requirements / interceptions** — `[AFTER]` UK (APHA), EU (EUROPHYT),
  Japan (MAFF), South Korea (APQA), Switzerland (BLW), Hong Kong (AFCD)

### Stage 5 — Wholesale
- **Wholesale £/kg** — `[NOW]` UK (DEFRA, Jun–Nov) · `[AFTER]` UK year-round (NCG, request)

### Stage 6 — Retail (shelf)
- **Retail shelf £/kg by retailer × tier × pack** — `[NOW]` UK (Trolley)
- **Retail price history** — `[NOW]` UK (ONS) · `[AFTER]` ONS scanner (2026), own-brand
  split, promotions/discount depth
- *(units sold, market share — paid §4; origin/variety on shelf — gap §5)*

### Stage 7 — Consumer / demand
- **Search interest** — `[AFTER]` UK (Google Trends)
- **Household consumption / penetration** — `[AFTER]` UK (DEFRA Family Food, lagged)
- **Reviews / sentiment** — `[AFTER]` UK (retailer scrape)
- *(price elasticity — derived/gap)*

### Cross-cutting
- **FX USD/GBP (+crosses)** — `[NOW]` (Frankfurter/ECB)
- **Per-year coverage/quality** — `[NOW]` (`coverage_by_year`)
- **Tariffs / duties** — `[AFTER]` (UK Trade Tariff)
- **Production / export forecasts** — `[NOW]` Peru (USDA-FAS) · `[AFTER]` Mexico, China,
  Spain, USA, South Africa, Canada (USDA-FAS GAIN / national)

---

## 4. The PAID ceiling — measurable only by buying (13 types, stays unmeasured)
actual yield/ha · bill-of-lading exporter→importer identity · importer→retailer price ·
importer identity (consignee) · named grower→orchard→GGN cert · organic vs conventional
area · production cost $/kg · reefer freight rate · retailer market share · shipment-level
export with exporter names · units sold / sales value · vessel/line/container · wastage/shrink.

These three unlocks are what free data structurally can't give: **identity join
(shipper↔importer)**, **demand quantity (units sold/share)**, **real cost (yield/freight)**.

## 5. STRUCTURAL gaps — collected nowhere, free or paid (16 types)
country-of-origin on shelf · variety on shelf · cultivar per shipment (ex-Chile) ·
per-block variety×planting-year census (ex-Chile) · harvest progress/timing · packhouse
throughput · volume by variety/organic at border · sub-monthly/weekly import volume ·
importer margin · price elasticity · pesticide/agrochemical use · phyto certificate per
consignment · variety mix (most origins) · per-country domestic production where the NSO
doesn't break out blueberry · forecast where no post publishes one.

---

## 6. One-line state
**Now:** the global flow+price spine (Comtrade, all lanes) + a deep Chile reference +
UK demand chain. **After max:** that spine, plus structure/phyto/forecast/condition/
demand overlays on every material origin and market — the entire *free* frontier, with
the paid (13) and structural-gap (16) boundaries explicitly drawn. **Then:** flip HS, repeat.
