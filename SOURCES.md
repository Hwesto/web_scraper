# Data sources

A living catalogue of every feed behind the dashboard — what each gives, how far it
reaches across the **exporter × importer** grid, and where it can grow. Status tags:

`LIVE` wired & refreshing · `DERIVED` computed from another feed · `PROXY` stand-in with a
documented gap · `STUB` schema fixed, collection forward-only · `BLOCKED` reachable only off
the sandbox/paid · `CANDIDATE` researched, not yet wired.

Each dashboard block is stamped with the source(s) below; empty cells in the coverage
matrix are sources we don't yet have for that pair.

---

## Current sources

### Flow & volume (the anchor)

| Source | Module | Provides | Scope | Cadence / lag | Status | Expand |
|---|---|---|---|---|---|---|
| **HMRC OTS** | `data/hmrc.py` | UK imports by origin — net mass + customs value, CN8 08104050 | Importer=UK, all origins | Monthly, ~6 wk lag | `LIVE` | Vintages only accrue forward (no deep revision history yet); add other CN8 lines / frozen 08111000 |
| **Chile Aduana — DUS cargo** | `scripts/fetch_chile_weekly_exports.py` | Chile→UK shipments, **named exporter/producer + cultivar + region**, weekly | Exporter=Chile, importer=UK | Weekly | `LIVE` | The deep, de-anonymised feed; daily DUS exists on datos.gob.cl but is `BLOCKED` (TLS) — would give true daily shape |
| **ODEPA (Chile customs mirror)** | `volume/data/odepa_chile.py` | Chile→UK export tonnes, official | Exporter=Chile, importer=UK | Monthly | `LIVE` | Two-sided cross-check; other destinations beyond UK |
| **Fused UK supply** | `volume/uk_total.py` | Year-round all-origin UK supply, never-blank | Importer=UK, 9 origins | Weekly | `DERIVED` | Add origins as live feeds appear (Peru/Morocco have none yet) |

### Prices

| Source | Module | Provides | Scope | Cadence / lag | Status | Expand |
|---|---|---|---|---|---|---|
| **HMRC unit value** | `price.py` | UK-landed **CIF £/kg per origin** (value÷volume) — every supplier, one method | Importer=UK, ~46 origins | Monthly | `DERIVED` | Volume-weight to kill tiny-N spikes; pair with origin FOB (done) |
| **UN Comtrade — destinations** | `market/comtrade.py` | What each market pays Chile (CIF $/kg) | Exporter=Chile, importer=all | Annual | `LIVE` | Premium Comtrade+ gives monthly; more HS lines |
| **UN Comtrade — origin export** | `market/origin_prices.py` | Every origin's **export FOB $/kg** to World + UK | All exporters, importer=World/UK | Annual | `LIVE` | More reporters; the FOB→CIF wedge (`origin_prices.wedge`) |
| **DEFRA wholesale** | `data/defra_price.py` | UK wholesale £/kg | Importer=UK | Weekly→fortnightly, **Jun–Nov only** | `LIVE` | Inherently seasonal — silent in the Chile (Dec–May) window |
| **ONS retail** | `data/ons_price.py` | UK retail blueberry £/kg 2018→Jan-2025, then all-berry index proxy → 2026 | Importer=UK | Monthly | `LIVE` + `PROXY` | Replace proxy when ONS scanner data lands (2026) |
| **Live retail (Trolley)** | `data/retail_price.py` | Multi-retailer shelf £/kg, blueberry-specific | Importer=UK | Weekly, forward-only | `LIVE` | No history (can't backtest); more products; **Kaggle history** (below) |

### Structure, access & experimental

| Source | Module | Provides | Scope | Status | Expand |
|---|---|---|---|---|---|
| **Catastro Frutícola** | `farm/data/catastro.py` → `capacity.py` | Chile orchard area by planting-year/variety/region → bearing-capacity forecast | Exporter=Chile | `LIVE` | No yield/destination/named entity (paid CIREN directory) |
| **SAG China roster** | `farm/sag_china.py` | 3,966 China-authorised Chilean orchards → who can chase the Asia premium | Exporter=Chile, importer=China | `LIVE` | Packing-facilities sheet; same trick for cherries/other crops |
| **GlobalG.A.P. certs** | `farm/certs.py` | UK-cert status inference; GGN validate/enrich | Exporter=Chile | `DERIVED` | No free name→GGN discovery; enrich only from an out-of-band GGN |
| **Satellite NDVI** | `data/ndvi.py` | Crop greenness (structurally leading) | Per origin | `LIVE` | Weak/confounded under polytunnels; per-origin tuning |
| **Packhouse hiring** | `data/altdata/job_boards.py` | Temp-role postings as a leading wave signal | Per origin | `STUB` | Forward-only; live per-board scrape is the TODO |

---

## New candidate sources

| Candidate | Would add | Fills (exp→imp) | Feasibility |
|---|---|---|---|
| **Kaggle "Time-Series UK Supermarket Data"** | Daily multi-retailer (Aldi/Asda/Morrisons/Tesco/Sainsbury's) shelf £/kg with **history from Jan-2024** + price/unit + own-brand | Global→UK retail, *with* backtest history | Free, but needs a Kaggle API token; community-maintained (staleness risk); **licence to confirm**. Best near-term upgrade to the forward-only Trolley scrape |
| **ONS grocery scanner data** | ~50% of the UK grocery market, official, item-level | Global→UK retail, definitive | Official roll-in from **2026** (parallel-run first); watch for a public cut |
| **Eurostat COMEXT** | EU import/export volumes & prices | Spain/NL/Poland exporter detail; EU as importer | Free, bulk API; good for the European cells |
| **Peru SUNAT / Agrodata Peru** | Peru export volume + price by destination | **Peru→UK / →World** (currently empty) | Agrodata partly free; SUNAT bulk patchy — would light up the Peru row |
| **Morocco — Office des Changes / EACCE** | Morocco export detail | Morocco→UK | Likely limited/paid; verify reachability |
| **GACC (China customs)** | China import registered establishments / volumes | exporter=all → China | Chinese-language portal; pairs with the SAG side we hold |
| **USDA / US customs (USA Trade)** | US import & export detail | US as importer/exporter | Free; useful for the US column |
| **Trolley.co.uk** | Aggregated multi-retailer (current `LIVE` scrape) | Global→UK retail | Proprietary, `robots.txt` disallows `/search/`; we poll a fixed `/product/` basket only — fragile, no history |

---

## The recurring gaps (no free source yet)

1. **Importer→retailer wholesale price** — the link between CIF (~£5.5/kg) and shelf (~£12/kg). No public feed; needs trade contacts.
2. **Costs / margins** — grower production cost, importer markup. Not in any customs data.
3. **Daily Chilean DUS** — exists, but datos.gob.cl is TLS-`BLOCKED` from the sandbox; weekly shape is modelled, not measured.
4. **Named → GGN / orchard identity** — no free name search (CIREN paid, GlobalG.A.P. validate-only).
5. **Demand side** — promotions, retailer orders, consumption.

> Verify reachability before wiring any candidate (the project's standing rule), and stamp
> each new feed onto the dashboard block(s) it powers.
