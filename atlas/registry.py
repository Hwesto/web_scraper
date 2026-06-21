"""The atlas registry: load / save / seed / query the free|paid|none catalogue.

The committed table lives at `data/atlas/registry.csv`. `seed()` (re)builds it
from the knowledge already pinned in `baseline_chile-uk.md`,
`baseline_peru-uk.md`, `SOURCES.md` and `DATA.md`, transcribed into machine
rows so the catalogue is queryable and scales to global × multi-fruit.

The markdown status glyphs map onto two orthogonal columns:
    ✅ held & wired (free)      -> access=free,  wired=yes
    🟢 free, not yet wired      -> access=free,  wired=no   (extends the free ceiling)
    💷 paid only (named)        -> access=paid,  wired=no
    ⛔ no source at any price    -> access=none,  wired=na
    derived (computed)          -> access=free,  wired=derived
A ⛔/💷 ("no free, paid exists") row is access=paid with a note; a 🟢/💷 row is
access=free (a free path exists) with the paid alternative in notes.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

from atlas import ATLAS_DIR
from atlas import schema

CACHE = ATLAS_DIR / "registry.csv"
_TODAY = "2026-06-19"                                   # this catalogue pass

# Fields per seed tuple (commodity+hs_code are constant for the blueberry seed).
_FIELDS = ["country", "role", "data_point", "access", "wired", "source",
           "url", "granularity", "depth", "verified_date", "notes"]
_HS = "081040"
_COMMODITY = "blueberry"

# Each tuple == one (country, role, data_point) row. Transcribed from the baselines.
_SEED: list[tuple] = [
    # ---- Chile, exporter side (the deep reference lane) ----
    ("Chile", "exporter", "orchard area by region/variety/planting-year", "free", "yes",
     "Catastro Frutícola (CIREN-ODEPA)", "datos.odepa.gob.cl", "block-level, ~3-yr rotation",
     "1987->2024", _TODAY, "manual snapshot; the structural base"),
    ("Chile", "exporter", "bearing-capacity trajectory", "free", "derived",
     "derived (capacity.py)", "", "planting-age x yield curve", "1987->2024", _TODAY,
     "assumption-based yield curve, documented"),
    ("Chile", "exporter", "variety-renewal trajectory", "free", "derived",
     "derived (capacity.py)", "", "by variety", "1987->2024", _TODAY,
     "from Catastro planting-year x variety"),
    ("Chile", "exporter", "actual yield per hectare", "paid", "no",
     "CIREN paid directory / iQonsulting", "", "orchard", "", "", "not in free Catastro"),
    ("Chile", "exporter", "production cost $/kg (inputs, labour)", "paid", "no",
     "iQonsulting / ODEPA ad-hoc studies", "", "", "", "",
     "the margin gap; no free per-kg feed"),
    ("Chile", "exporter", "named grower -> orchard -> GGN cert", "paid", "no",
     "CIREN (named) / GlobalG.A.P. validate-only", "ggn.org/search.html", "named", "", "",
     "no free name->GGN discovery"),
    ("Chile", "exporter", "organic vs conventional area", "paid", "no",
     "certifier registries", "", "", "", "", "only partial free hints"),
    ("Chile", "exporter", "weather / frost / chill-hours (growing regions)", "free", "no",
     "NASA POWER / NOAA / Meteochile", "power.larc.nasa.gov", "point/regional", "", "",
     "free, leading; not wired"),
    ("Chile", "exporter", "NDVI greenness (Chilean regions)", "free", "probe",
     "NASA/ORNL MODIS; Sentinel-2", "modis.ornl.gov/rst", "250m / 10m", "", _TODAY,
     "module exists (Spain/Morocco); Chile coded, throttle-flaky"),
    ("Chile", "exporter", "drought / water-allocation index", "free", "no",
     "Chilean DGA / NASA", "dga.mop.gob.cl", "regional", "", "", "free, not wired"),
    ("Chile", "exporter", "pesticide / agrochemical use", "none", "na",
     "", "", "", "", "", "not public at any price"),
    ("Chile", "exporter", "packhouse hiring (labour demand, leading)", "free", "no",
     "job boards / agency pages", "", "forward-only", "", "",
     "stub; no history, forward signal"),
    ("Chile", "exporter", "China-authorised orchards + packing facilities", "free", "yes",
     "SAG China roster", "sag.gob.cl/.../exportaciones/registros", "3,966 orchards, named",
     "season", _TODAY, "weekly cron"),
    ("Chile", "exporter", "harvest progress / timing by region", "none", "na",
     "", "", "", "", "", "proxy via exports/NDVI only"),
    ("Chile", "exporter", "packhouse throughput", "none", "na",
     "", "", "", "", "", "proxy via hiring (weak)"),
    ("Chile", "exporter", "volume Chile->UK, weekly", "free", "yes",
     "Chile Aduana DUS", "datos.gob.cl", "weekly, named, de-anonymised", "2018->now", _TODAY,
     "clean-egress cron (TLS-blocked from sandbox)"),
    ("Chile", "exporter", "FOB price Chile->UK, weekly", "free", "yes",
     "Chile Aduana DUS", "datos.gob.cl", "USD/kg, weekly", "2018->now", _TODAY, "declared"),
    ("Chile", "exporter", "named exporter (RUT, comuna)", "free", "yes",
     "Chile Aduana DUS", "datos.gob.cl", "named entity", "2018->now", _TODAY, ""),
    ("Chile", "exporter", "named producer / marca", "free", "yes",
     "Chile Aduana DUS", "datos.gob.cl", "~72 named", "2018->now", _TODAY, ""),
    ("Chile", "exporter", "cultivar per shipment", "free", "yes",
     "Chile Aduana DUS", "datos.gob.cl", "declared on ~half", "2018->now", _TODAY,
     "DUS carries cultivar (Peru's SUNAT does not)"),
    ("Chile", "exporter", "region of origin", "free", "yes",
     "Chile Aduana DUS", "datos.gob.cl", "region", "2018->now", _TODAY, ""),
    ("Chile", "exporter", "realised CIF $/kg by destination", "free", "yes",
     "UN Comtrade (reporter=Chile)", "comtradeapi.un.org", "annual, per partner",
     "2012->2025", _TODAY, "value/weight = realised price each market pays"),
    ("Chile", "exporter", "export FOB $/kg (World + UK)", "free", "yes",
     "UN Comtrade (reporter=Chile)", "comtradeapi.un.org", "annual", "2012->2025", _TODAY,
     "origin-side unit value -> FOB->CIF wedge"),
    ("Chile", "exporter", "volume Chile->UK, daily", "free", "no",
     "datos.gob.cl daily DUS", "datos.gob.cl", "daily", "", "",
     "TLS-blocked from our egress; needs clean fetch"),
    ("Chile", "exporter", "port of loading", "free", "no",
     "Chile Aduana DUS", "datos.gob.cl", "per shipment", "", "", "likely present, not yet extracted"),
    ("Chile", "exporter", "bill of lading: exporter -> UK consignee", "paid", "no",
     "Panjiva (S&P) / ImportGenius / Datamyne", "", "per shipment", "", "",
     "the shipper<->importer identity join"),
    ("Chile", "exporter", "vessel / shipping line / container count", "paid", "no",
     "Panjiva / ImportGenius / Datamyne; AIS", "", "per shipment", "", "", ""),
    ("Chile", "exporter", "phyto certificate per consignment", "none", "na",
     "SAG (per-consignment, not bulk)", "", "", "", "", ""),
    ("Chile", "exporter", "reefer freight rate Chile->UK", "paid", "no",
     "Xeneta / Freightos FBX / Drewry", "", "lane", "", "",
     "we use a documented reefer/payload assumption"),

    # ---- Peru, exporter side (flow rich, no orchard census) ----
    ("Peru", "exporter", "orchard area by region", "free", "no",
     "MIDAGRI / USDA-FAS / committee reports", "midagri.gob.pe", "regional aggregates",
     "", "", "no per-block census (2023 ~18.6k ha)"),
    ("Peru", "exporter", "per-block variety x planting-year census", "none", "na",
     "", "", "", "", "",
     "no Peruvian Catastro -- the key asymmetry; capacity/renewal cannot be built"),
    ("Peru", "exporter", "variety mix", "none", "na",
     "committee reports (qualitative)", "", "", "", "",
     "Biloxi/Ventura/Sekoya/Rocio; not a structured feed"),
    ("Peru", "exporter", "realised FOB/CIF $/kg by destination", "free", "yes",
     "UN Comtrade (reporter=Peru)", "comtradeapi.un.org", "annual, per partner",
     "2012->2025", _TODAY, "Peru netback; US/NL/HK/UK/China destinations"),
    ("Peru", "exporter", "named exporter", "free", "yes",
     "Agrodata / SUNAT (ProArandanos season)", "agrodataperu.com", "named, annual season", "", _TODAY,
     "DEPTH FRONTIER -- wired via atlas/peru_exporters.py (top-15 by volume+FOB+YoY, "
     "2024/25: Camposol 34kt/$259M ...); annual snapshot, live SUNAT-weekly still gated"),
    ("Peru", "exporter", "cultivar per shipment", "none", "na",
     "", "", "", "", "", "SUNAT customs does not carry cultivar (unlike Chile DUS)"),
    ("Peru", "exporter", "season export progress, by week", "free", "yes",
     "ProArandanos (via agri-press)", "proarandanos.pe", "season snapshot", "", _TODAY,
     "REAL-TIME LAYER -- wired via atlas/campaigns.py (2025/26: ~383kt record ▲20%, "
     "peak wk40 21kt); site is a dashboard/ECONNREFUSED so it's a hand-curated press snapshot, "
     "not a live weekly feed"),
    ("Peru", "exporter", "area / production / exports + forecasts", "free", "yes",
     "USDA-FAS Blueberry Annual (Lima)", "apps.fas.usda.gov/newgainapi", "PSD table, annual",
     "2022/23->2026/27", _TODAY, "the Catastro substitute; manual annual bump"),
    # ---- current-season frontier (the ProArandanos analog per country; see FRONTIER_SOURCES.md) ----
    ("Chile", "exporter", "current-season export tracker", "free", "yes",
     "Comite de Arandanos / Frutas de Chile (iQonsulting)", "https://frutasdechile.cl/committee/arandanos/",
     "weekly PDF crop report", "2025/26", _TODAY,
     "REAL-TIME -- wired via atlas/campaigns.py (2025/26 fresh ~92kt; frozen 72kt); weekly PDF, predictable URL (MEDIUM)"),
    ("South Africa", "exporter", "current-season export tracker", "free", "yes",
     "Berries ZA (formerly SABPA) export reports", "https://berriesza.co.za/export-reports/",
     "weekly PDF, AUTO-PARSED", "2025/26", _TODAY,
     "REAL-TIME AUTOMATED -- atlas/berriesza.py finds the latest weekly PDF and parses the "
     "year-to-date-by-region table (2025/26 wk4: 25.8kt; Europe 11kt, UK 10kt, ME 3kt); the runner "
     "re-parses each week. The one committee PDF that's a clean table (Chile=charts, Argentina=stale)"),
    ("Argentina", "exporter", "current-season export tracker", "free", "yes",
     "ABC -- Argentine Blueberry Committee", "https://www.argblueberry.com/home/en/reportes/",
     "weekly PDF", "2025", _TODAY,
     "REAL-TIME -- wired via atlas/campaigns.py (~6kt; US 33%/NL 25%); per-week PDFs (MEDIUM)"),
    ("Mexico", "exporter", "current-season export tracker", "free", "yes",
     "Aneberries (via press)", "https://aneberries.mx/", "weekly, member-gated -> press", "2023/24", _TODAY,
     "wired via atlas/campaigns.py (~79kt); weekly data member-gated, surfaces via press (SNAPSHOT)"),
    ("Spain", "exporter", "current-season export tracker", "free", "yes",
     "FEPEX (Aduanas) + Freshuelva + Junta de Andalucia Observatorio", "https://www.fepex.es/datos-del-sector/exportacion-importacion-espanola-frutas-hortalizas",
     "FEPEX Excel + weekly Andalucia PDF", "2025", _TODAY,
     "wired via atlas/campaigns.py (2025 exports 100kt; Huelva 63kt); FEPEX Excel EASY, Observatorio weekly PDF MEDIUM"),
    ("Morocco", "exporter", "current-season export tracker", "free", "yes",
     "APEFEL / EastFruit (press)", "https://east-fruit.com/", "press", "2024/25", _TODAY,
     "wired via atlas/campaigns.py (~82kt ▲20%); Foodex BI is gated, so press SNAPSHOT only"),
    ("USA", "both", "weekly shipment movement + FOB price by origin", "free", "yes",
     "USDA-AMS Market News (WA_FV408 movement; + FOB reports)", "https://www.ams.usda.gov/mnreports/wa_fv408.txt",
     "weekly + season-to-date, by origin", "to 2024/25", _TODAY,
     "wired via atlas/usda_movement.py -- UNIQUE: US supply by origin incl. domestic states "
     "(Georgia 21kt, Michigan 14kt) + import arrivals (Peru 61kt, Canada 24kt) season-to-date. "
     "Keyless TXT mirror runs to ~early-2025; LIVE weekly needs the free MARS API key (slug 3251)"),
    ("Canada", "both", "production / area / value (annual)", "free", "no",
     "Statistics Canada table 32-10-0364-01 (WDS API)", "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210036401",
     "annual, CSV + JSON API", "2024", "", "EASY API (2024: 165.6kt; highbush 71.5kt) but annual/lagged -- backbone not frontier"),
    ("Portugal", "exporter", "current-season export tracker", "none", "na",
     "(no grower-committee feed)", "", "", "", "",
     "no ProArandanos analog; only lagging INE/GPP annual area (~21kt 2023) -- the lagging source we beat"),
    ("Peru", "exporter", "Peru->China GACC phyto roster", "free", "no",
     "GACC-registered orchards / APHIS", "", "named orchards", "", "",
     "SAG-China analogue, if the GACC list is fetchable"),

    # ---- United Kingdom, importer side (lane-independent destination layer) ----
    ("United Kingdom", "importer", "import volume by origin (tonnes)", "free", "yes",
     "HMRC OTS", "api.uktradeinfo.com", "monthly, CN8 08104050, ~46 origins", "2018->now",
     _TODAY, "the anchor, ~6wk lag"),
    ("United Kingdom", "importer", "import value -> CIF GBP/kg by origin", "free", "derived",
     "HMRC OTS (value/mass)", "api.uktradeinfo.com", "monthly, per origin", "2018->now",
     _TODAY, "derived unit value"),
    ("United Kingdom", "importer", "fresh vs frozen split", "free", "no",
     "HMRC (frozen CN 0811...)", "api.uktradeinfo.com", "monthly", "", "", "not yet pulled"),
    ("United Kingdom", "importer", "port of entry", "free", "no",
     "HMRC RTS (partial); BoL (paid)", "api.uktradeinfo.com", "", "", "", "partial free"),
    ("United Kingdom", "importer", "importer identity (consignee)", "paid", "no",
     "Panjiva / ImportGenius / Datamyne", "", "named", "", "", "the wholesale-link join"),
    ("United Kingdom", "importer", "import volume, weekly/daily", "none", "na",
     "", "", "", "", "", "HMRC is monthly; no free sub-monthly UK customs"),
    ("United Kingdom", "importer", "volume by variety / organic at border", "none", "na",
     "", "", "", "", "", "single CN code, type-blind"),
    ("United Kingdom", "importer", "phyto interceptions / rejections at border", "free", "no",
     "APHA / PHSI plant-health publications", "gov.uk", "incident", "", "", "free-ish, verify"),
    ("United Kingdom", "importer", "wholesale price GBP/kg", "free", "yes",
     "DEFRA", "gov.uk/.../statistical-data-sets", "weekly, Jun-Nov only", "2018->now", _TODAY,
     "silent Dec-May (the Chile window)"),
    ("United Kingdom", "importer", "wholesale price, year-round", "free", "no",
     "New Covent Garden (request-only)", "newcoventgardenmarket.com", "", "", "",
     "semi-free; request-only"),
    ("United Kingdom", "importer", "importer -> retailer price", "paid", "no",
     "trade contacts (no public feed)", "", "", "", "", "the biggest single gap"),
    ("United Kingdom", "importer", "importer margin", "none", "na",
     "", "", "", "", "", "derived/estimated only"),
    ("United Kingdom", "importer", "wastage / shrink rates", "paid", "no",
     "Kantar / WRAP", "", "", "", "", ""),
    ("United Kingdom", "importer", "retail shelf price GBP/kg, multi-retailer", "free", "yes",
     "Trolley", "trolley.co.uk/product", "weekly, retailer x tier x pack", "forward", _TODAY,
     "standard/organic/finest, 125-500g"),
    ("United Kingdom", "importer", "retail price history (year-round)", "free", "yes",
     "ONS", "ons.gov.uk", "monthly", "2018->2026", _TODAY, "all-berry proxy after Jan-2025"),
    ("United Kingdom", "importer", "grocery scanner data (~50% of market)", "free", "no",
     "ONS", "ons.gov.uk", "official", "", "", "rolls in 2026"),
    ("United Kingdom", "importer", "promotions / discount depth", "free", "no",
     "own scrape; Assosia (paid)", "", "weekly", "", "", "scrapeable; Assosia is the paid feed"),
    ("United Kingdom", "importer", "own-brand vs branded", "free", "no",
     "Trolley flag", "trolley.co.uk", "", "", "", "partial"),
    ("United Kingdom", "importer", "country of origin on shelf", "none", "na",
     "", "", "", "", "", "rotates weekly, unlabelled online"),
    ("United Kingdom", "importer", "variety on shelf", "none", "na",
     "", "", "", "", "", "never labelled in retail"),
    ("United Kingdom", "importer", "units sold / sales value", "paid", "no",
     "Kantar / NielsenIQ / Circana", "", "", "", "", "the demand quantity"),
    ("United Kingdom", "importer", "retailer market share", "paid", "no",
     "Kantar", "", "", "", "", ""),
    ("United Kingdom", "importer", "search interest", "free", "no",
     "Google Trends", "trends.google.com", "weekly", "", "", "free, leading-ish"),
    ("United Kingdom", "importer", "household consumption / penetration", "free", "no",
     "DEFRA Family Food (free, lagged); Kantar (paid)", "gov.uk", "annual", "", "", ""),
    ("United Kingdom", "importer", "price elasticity", "none", "na",
     "", "", "", "", "", "derived only"),
    ("United Kingdom", "importer", "reviews / sentiment", "free", "no",
     "retailer review scrape", "", "", "", "", "noisy"),

    # ---- Global / cross-cutting (country = *) ----
    ("*", "global", "bilateral flow + price matrix (exporter x importer)", "free", "yes",
     "UN Comtrade (HS 081040)", "comtradeapi.un.org", "annual; monthly many reporters",
     "2012->2025", _TODAY,
     "the free global base layer; wired via atlas/comtrade_matrix.py -> data/atlas/comtrade_bilateral.csv (realised USD/kg per lane, exporter target set)"),
    ("*", "global", "bilateral MONTHLY flow + price (seasonality)", "free", "yes",
     "UN Comtrade monthly (HS 081040)", "comtradeapi.un.org", "monthly, per lane, exporter target set",
     "2023->now", _TODAY,
     "the counter-season relay; wired via atlas/comtrade_monthly.py -> data/atlas/comtrade_monthly.csv; seasonality() gives each origin's monthly volume profile"),
    ("*", "global", "blueberry area / production / yield by country", "free", "yes",
     "FAOSTAT (QCL bulk, item 552)", "https://bulks-faostat.fao.org/production/",
     "annual, by country", "1961->now", _TODAY,
     "the global production base layer (FAO is to growing what Comtrade is to trade); "
     "wired via atlas/faostat.py -> data/atlas/faostat_blueberry.csv; FAO area incl. wild lowbush for US/CA"),
    ("*", "global", "growing-region weather / frost / precipitation", "free", "yes",
     "NASA POWER (monthly, AG community)", "https://power.larc.nasa.gov/api/temporal/monthly/point",
     "monthly, per growing region (temp/min/max, precip)", "1981->now", _TODAY,
     "the condition base layer; wired via atlas/nasa_power.py -> data/atlas/weather_regions.csv; "
     "14 regions, frost risk via T2M_MIN; finer NDVI layers on top"),
    ("*", "global", "FX USD/GBP (and crosses)", "free", "yes",
     "Frankfurter / ECB", "api.frankfurter.app", "daily", "daily", _TODAY,
     "replaces notional 0.79"),
    ("*", "global", "tariffs / duties into UK", "free", "no",
     "UK Trade Tariff", "trade-tariff.service.gov.uk", "per origin", "", "",
     "fresh blueberries 0% under UK-Chile / UK-Andean; confirm & note"),
    ("*", "global", "production / export forecasts", "free", "yes",
     "USDA-FAS GAIN (Blueberry Annual)", "apps.fas.usda.gov/newgainapi", "season-ahead, MT", "", _TODAY,
     "the forward axis; wired via atlas/usda_gain.py -> data/atlas/usda_forecasts.csv (Peru+Mexico "
     "headline forecasts) + scripts/fetch_usda_peru.py (full Peru PSD); China report qualitative; "
     "filenames hand-pinned (no free GAIN search)"),
    ("*", "global", "EU detailed trade by HS6/CN8 (all member states)", "free", "yes",
     "Eurostat COMEXT (DS-045409)", "https://ec.europa.eu/eurostat/api/comext/dissemination",
     "annual, HS6 081040 x reporter x partner x flow", "2002->now", _TODAY,
     "no key; wired via atlas/eurostat.py -> data/atlas/eurostat_blueberry.csv (ES/NL/PL/DE/FR/PT/BE/IT/AT, EUR/kg)"),
    ("*", "global", "global trade reconciliation + backtest", "free", "derived",
     "atlas/global_reconcile.py (Comtrade x Eurostat x US x Asia x UK x committees)", "", "per-origin per-year", "2022->2026", _TODAY,
     "the accounting identity exports=world-imports. GLOBAL BACKTEST: mirror_ratio median 1.10. "
     "Current EU+US+Asia+UK accounted: Peru 92%, Chile 100%, S.Africa 96%, Morocco 87%, Mexico 82% -- "
     "residual = Canada/Gulf/Russia. EU live(2026); US/UK one-key-or-HMRC away; Asia=Comtrade "
     "(China GACC gated -- the one bloc with no free current feed). -> data/atlas/global_reconcile.csv"),
    ("China", "importer", "blueberry imports by origin (live)", "free", "yes",
     "GACC via press/resellers (Tridge/Agronometrics/Produce Report)", "http://stats.customs.gov.cn/", "annual snapshot", "2024->2025", _TODAY,
     "SNAPSHOT -- wired via atlas/china.py (2024 ~38.7kt, Peru 89%; 2025 Peru +153% Chancay). "
     "GACC portal is JS-challenge anti-bot gated (412; translating won't help), so press-curated like "
     "committees. Comtrade backstops lagged (mainland 39kt + HK 30kt 2024)"),
    ("China", "producer", "domestic production (world #1)", "free", "yes",
     "China Daily / GACC via press (FAOSTAT has NO China blueberry)", "https://www.chinadaily.com.cn/", "annual snapshot", "2020->2025", _TODAY,
     "the world's #1 producer, INVISIBLE in FAOSTAT -- wired via atlas/china.py: 810kt 2025 (2x in 5yr; "
     "vs USA 402kt/Peru 354kt), Yunnan 280kt. Domestic oversupply crashed prices -50% -> a risk to the "
     "Peru->China premium-import pivot. Snapshot (China Daily 2026-04)"),
    ("USA", "importer", "US imports by origin (live)", "free", "no",
     "US Census intltrade/imports/hs (HTS 0810.40)", "https://api.census.gov/data/timeseries/intltrade/imports/hs",
     "monthly, by country", "current", "",
     "atlas/uscensus.py -- the live US slice, ONE FREE KEY away (set CENSUS_API_KEY); until then "
     "global_reconcile uses the Comtrade US slice (174kt Peru 2024). Same contract as the AMS MARS key"),
    ("*", "global", "EU MONTHLY bilateral trade (current, beats Comtrade lag)", "free", "yes",
     "Eurostat COMEXT monthly (DS-045409, freq=M)", "https://ec.europa.eu/eurostat/api/comext/dissemination",
     "MONTHLY, all 27 EU reporters x partner x flow", "2019->2026-04", _TODAY,
     "wired via atlas/eurostat_monthly.py -> eurostat_monthly.csv; current to 2026-04 (~14mo ahead of "
     "Comtrade). BACKTESTED vs Comtrade 2022-24: median |diff| 9.4% (eurostat_backtest.csv). "
     "2025 EU imports: Peru 98kt, Morocco 54kt, Chile 35kt. The near-Comtrade current layer for the EU bloc"),
]

# ---- Phase 2: national overlay sources per country in the Comtrade target set ----
# Probe reachability, do NOT wire (the standing rule). One+ row per country x overlay
# category (customs detail / shipment-level identity / phyto registry / area census /
# forecast). Sources compiled + URL-verified 2026-06; reachability probed from this
# sandbox (verified_date set where a live 200 was seen; blank where the source is
# real but anti-bot/503-blocked here -> re-probe on the clean-egress runner).
# Recurring finding: NO country publishes free shipment-level export data with
# exporter names -- that identity layer is paid (brokers) everywhere, like Chile/Peru.
_SEED_PHASE2: list[tuple] = [
    # ---- Spain (EU; #3 exporter 2023) ----
    ("Spain", "exporter", "national customs trade detail (CN8, province)", "free", "no",
     "DataComex (Agencia Tributaria) + Eurostat COMEXT", "https://datacomex.comercio.es/",
     "HS/TARIC x partner x province, monthly", "", _TODAY,
     "aggregate; CN 08104050; bulk needs free login. COMEXT for harmonised CN8"),
    ("Spain", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers (Volza / ImportGenius / Tendata)", "", "per shipment", "", "",
     "no free origin bill-of-lading -- the identity gap, as everywhere"),
    ("Spain", "exporter", "authorised export orchards/packhouses (phyto)", "none", "na",
     "MAPA CEXVEG", "https://servicio.mapa.gob.es/cexvegweb/home", "operator-level", "", "",
     "registration-gated internal registry; no public list found"),
    ("Spain", "exporter", "orchard / planted-area by region/variety", "free", "no",
     "MAPA ESYRCE", "https://www.mapa.gob.es/es/estadistica/temas/estadisticas-agrarias/agricultura/esyrce/",
     "plot-level survey by Autonomous Community, annual", "1990->now", _TODAY,
     "berries/frutos rojos; a Catastro analogue (plot-level since 1990)"),
    ("Spain", "exporter", "production/export forecast", "free", "no",
     "USDA-FAS GAIN 'Spanish Berry Outlook' (Madrid)", "https://www.fas.usda.gov/data",
     "season-ahead", "", "", "fas.usda.gov 403 to bots; live in browser/runner"),

    # ---- Netherlands (EU; #2 exporter 2023 -- re-export hub) ----
    ("Netherlands", "exporter", "national customs trade detail (re-export split)", "free", "no",
     "CBS StatLine + Eurostat COMEXT", "https://opendata.cbs.nl/",
     "value by SITC/CN8 x partner, monthly; free OData API", "2015->now", _TODAY,
     "distinguishes Dutch-product exports vs re-exports (key for NL hub)"),
    ("Netherlands", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers", "", "per shipment", "", "", "no free origin BoL"),
    ("Netherlands", "exporter", "authorised export orchards/packhouses (phyto)", "none", "na",
     "NVWA e-CertNL", "https://english.nvwa.nl/topics/themes/plant-health", "operator-level",
     "", "", "certification process only; no public registry"),
    ("Netherlands", "exporter", "orchard / planted-area (small fruit)", "free", "no",
     "CBS StatLine (klein fruit) + Landbouwtelling", "https://opendata.cbs.nl/", "national",
     "", _TODAY, "blueberry sits within 'small fruit'; no dedicated blueberry area table"),
    ("Netherlands", "exporter", "production/export forecast", "none", "na",
     "USDA-FAS EU-wide GAIN (no NL blueberry report)", "https://www.fas.usda.gov/data",
     "EU-level", "", "", "no dedicated NL blueberry forecast; folded into EU reporting"),

    # ---- Morocco (#5 exporter 2023) ----
    ("Morocco", "exporter", "national customs trade detail (by product)", "free", "no",
     "Office des Changes -- Base commerce extérieur", "https://services.oc.gov.ma/DataBase/CommerceExterieur/login",
     "product x partner, monthly since 1998, CSV", "1998->now", "",
     "free visitor tier (subscriber tier gated); login page 403 from sandbox"),
    ("Morocco", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers", "", "per shipment", "", "", "no free origin BoL"),
    ("Morocco", "exporter", "authorised export packing stations (phyto)", "free", "no",
     "ONSSA -- approved establishments list", "https://www.onssa.gov.ma/lists-of-approved-authorised-establishments/?lang=en",
     "named packing stations + agrement no., PDF", "", "",
     "the best public NPPO list of the set; 503 from sandbox -- re-probe on runner"),
    ("Morocco", "exporter", "orchard / planted-area (red fruits)", "free", "no",
     "Min. Agriculture -- Filiere petits fruits rouges", "https://www.agriculture.gov.ma/fr/filieres-regions/petits-fruits-rouges",
     "national/sector (area, production, export share)", "", "",
     "~2,175 ha 2022/23; regional figures in PDFs not an open DB; 503 from sandbox"),
    ("Morocco", "exporter", "production/export forecast", "none", "na",
     "USDA-FAS Rabat spotlight (no berry annual)", "https://fas.usda.gov/data/spotlight-morocco-fruit-exports",
     "analysis", "", "", "no dedicated season-ahead Morocco blueberry forecast found"),

    # ---- USA (#6 exporter, #1 importer 2023) ----
    ("USA", "both", "national customs trade detail (HTS10 / Schedule B, by state)", "free", "no",
     "USITC DataWeb; Census USA Trade Online / API", "https://dataweb.usitc.gov/",
     "HTS10 x partner x customs district / state, monthly", "", _TODAY,
     "DataWeb mostly no-login; Census API is free but key-gated (200+'Missing Key')"),
    ("USA", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers (Panjiva / ImportGenius / Datamyne)", "", "per shipment", "", "",
     "no free US export BoL; import manifests partly broker-available (paid)"),
    ("USA", "exporter", "authorised export orchards/packhouses (phyto)", "none", "na",
     "USDA APHIS PCIT / PExD", "https://www.aphis.usda.gov/plant-exports/certification",
     "operator-level", "", "", "registration-gated; no public orchard/packhouse registry"),
    ("USA", "exporter", "orchard / planted-area by state", "free", "no",
     "USDA NASS QuickStats + Noncitrus Fruits & Nuts", "https://quickstats.nass.usda.gov/",
     "bearing acreage/yield/production/value by state, annual", "", _TODAY,
     "no-login query tool; Census of Ag adds farm-level every 5 yrs"),
    ("USA", "exporter", "production/export forecast", "free", "no",
     "USDA-FAS GAIN (global) + NASS Noncitrus in-season", "https://www.fas.usda.gov/data/search",
     "season-ahead / in-season", "", "", "US covered in global overviews; no standalone US GAIN"),

    # ---- Mexico (#7 exporter 2023) ----
    ("Mexico", "exporter", "national customs trade detail (NICO 8-10 digit)", "free", "no",
     "INEGI BCMM + Banxico Cubo Comercio Exterior", "https://www.inegi.org.mx/rnm/index.php/catalog/1082",
     "fraccion/NICO x partner, monthly", "", _TODAY,
     "use INEGI/Banxico -- SIAVI is frozen at Nov 2021; aggregate, no exporter names"),
    ("Mexico", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers (pedimento data)", "", "per shipment", "", "", "no free SAT pedimentos"),
    ("Mexico", "exporter", "authorised export orchards (phyto)", "free", "yes",
     "SENASICA -- predios de berries (China)", "https://www.gob.mx/senasica/documentos/huertos-registrados",
     "named orchards: code, name, area-ha, municipio, estado, fruit", "", _TODAY,
     "wired via atlas/senasica.py -> data/atlas/mx_registered_orchards.csv (SAG-China analogue; 30 blueberry predios, China list)"),
    ("Mexico", "exporter", "orchard / planted-area by state/variety", "free", "no",
     "SIAP -- Cierre de la Produccion Agricola", "https://nube.agricultura.gob.mx/cierre_agricola/",
     "area/production/value by crop+variety+state+municipality, annual", "", "",
     "aranadano tracked; a Catastro analogue; 503 from sandbox -- re-probe on runner"),
    ("Mexico", "exporter", "production/export forecast", "free", "yes",
     "USDA-FAS GAIN 'Mexico Blueberry Annual' (Guadalajara)", "https://www.fas.usda.gov/data/mexico-blueberry-annual-voluntary",
     "season-ahead (MT)", "", _TODAY, "wired via atlas/usda_gain.py (CY2025: prod 73.5k / exp 70k / imp 20k MT)"),

    # ---- Canada (#8 exporter 2023) ----
    ("Canada", "both", "national customs trade detail (HS8 export / HS10 import)", "free", "no",
     "StatCan CIMT + ISED Trade Data Online", "https://ised-isde.canada.ca/site/trade-data-online/en",
     "HS x partner x province, monthly", "", _TODAY,
     "ISED no-login (verified); CIMT 503 from sandbox; aggregate, no exporter names"),
    ("Canada", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers", "", "per shipment", "", "", "no free Canadian export BoL"),
    ("Canada", "exporter", "authorised export orchards/packhouses (phyto)", "none", "na",
     "CFIA horticulture exports", "https://inspection.canada.ca/en/plant-health/horticulture/exports",
     "operator-level", "", _TODAY, "registration internal to CFIA; no public blueberry registry"),
    ("Canada", "exporter", "orchard / planted-area by province", "free", "no",
     "StatCan Fruit & vegetable production + Census of Agriculture", "https://www.statcan.gc.ca/en/census-agriculture",
     "area/production/value by province, annual + 5-yr census", "", _TODAY,
     "splits wild lowbush vs cultivated highbush"),
    ("Canada", "exporter", "production/export forecast", "free", "no",
     "AAFC Statistical Overview of the Canadian Fruit Industry", "https://www.agr.gc.ca/eng/horticulture/horticulture-sector-reports/",
     "annual (retrospective)", "", "", "no forward blueberry outlook -- only the annual overview"),

    # ---- South Africa (#9 exporter 2023) ----
    ("South Africa", "exporter", "national customs trade detail (HS x partner)", "free", "no",
     "SARS Trade Statistics", "https://www.sars.gov.za/customs-and-excise/trade-statistics/",
     "HS x partner, monthly; beta downloads (volume-limited)", "", _TODAY,
     "legislated trade-stats authority; aggregate, no exporter names"),
    ("South Africa", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers", "", "per shipment", "", "", "no free origin BoL"),
    ("South Africa", "exporter", "authorised export orchards/packhouses (phyto)", "free", "no",
     "DALRRD PUC/PHC + PPECB", "https://ppecb.com/", "PUC/PHC registration; per-crop PDFs",
     "", "", "framework public; no standalone blueberry PUC list found"),
    ("South Africa", "exporter", "orchard / planted-area (blueberry-specific)", "free", "no",
     "Berries ZA -- Statistics", "https://www.berriesza.co.za/statistics/",
     "ha + regional split, blueberry-specific", "", _TODAY,
     "best blueberry source (~2,600-3,000 ha; W.Cape ~60%); some member-gated"),
    ("South Africa", "exporter", "production/export forecast", "free", "no",
     "Berries ZA crop estimates + USDA-FAS GAIN (Pretoria)", "https://www.berriesza.co.za/",
     "season-ahead", "", _TODAY, "~25,000 t export estimate; NAMC fruit trade-flow adds context"),

    # ---- Poland (EU; #9-ish exporter 2023) ----
    ("Poland", "exporter", "national customs trade detail (CN8)", "free", "no",
     "GUS Foreign Trade + Eurostat COMEXT", "https://stat.gov.pl/en/topics/prices-trade/trade/",
     "HS/CN8 x partner, monthly", "", "",
     "GUS 503 from sandbox; COMEXT is the harmonised CN8 route (reachable)"),
    ("Poland", "exporter", "shipment-level export with exporter names", "paid", "no",
     "commercial brokers", "", "per shipment", "", "", "no free origin BoL"),
    ("Poland", "exporter", "authorised export orchards/packhouses (phyto)", "none", "na",
     "PIORIN -- Professional Operators Register", "http://piorin.gov.pl/en/",
     "operator-level", "", "", "registration required but no public named list published"),
    ("Poland", "exporter", "orchard / planted-area by voivodeship", "free", "no",
     "GUS Agriculture & horticultural crops + BDL", "https://stat.gov.pl/en/topics/agriculture-forestry/agricultural-and-horticultural-crops/",
     "area/production by voivodeship, annual", "", "",
     "borowka wysoka (highbush) in Statistical Yearbook of Agriculture; 503 from sandbox"),
    ("Poland", "exporter", "production/export forecast", "none", "na",
     "USDA-FAS Warsaw (no blueberry annual)", "https://www.fas.usda.gov/",
     "n/a", "", "", "Stone Fruits Annual excludes blueberry; no season-ahead PL forecast found"),
]

# ---- Phase 2b: importer-side + re-export-hub overlays (target-set continued) ----
# The big importers and re-export hubs beyond the exporters above. Same discipline
# (probe, don't wire). verified_date set where a live 200 was seen from this sandbox.
# Recurring findings: (1) re-exports are a distinct flow ONLY in Hong Kong's stats --
# EU/Germany/France fold them into total exports, so hub activity must be inferred;
# (2) no NPPO publishes a clean per-fruit approved-orchard list for blueberries --
# USDA-FAS GAIN is the best free summary of who may ship where.
_SEED_PHASE2B: list[tuple] = [
    # ---- Germany (#3 importer 2023; producer + re-export) ----
    ("Germany", "both", "national customs trade detail (CN8)", "free", "no",
     "Destatis GENESIS (51000) + Eurostat COMEXT", "https://www-genesis.destatis.de/genesis/online",
     "monthly, CN8 x partner, value+qty", "", "",
     "imports vs exports only -- re-exports folded into exports; 403 to bots from sandbox"),
    ("Germany", "importer", "plant-health import interceptions", "free", "no",
     "EU EUROPHYT/TRACES + JKI (NPPO)", "https://agrinfo.eu/book-of-reports/",
     "by commodity/origin/pest, monthly summaries", "", _TODAY,
     "live TRACES gated (authorities); EUROPHYT annual reports + AGRINFO free"),
    ("Germany", "exporter", "domestic blueberry area/harvest (Heidelbeeren)", "free", "no",
     "Destatis Strauchbeeren (412) + BMEL", "https://www.bmel-statistik.de/landwirtschaft/gartenbau/obstanbau/strauchbeeren",
     "national + Bundesland, ha + t", "", _TODAY, "real producer (~3,450 ha 2025)"),

    # ---- France (#10 importer 2023; producer + re-export) ----
    ("France", "both", "national customs trade detail (NC8)", "free", "no",
     "Le Kiosque (DGDDI) + Eurostat COMEXT", "https://lekiosque.finances.gouv.fr/",
     "monthly, NC8 x partner", "", _TODAY,
     "imports vs exports; no discrete re-export flow; open dumps on data.gouv.fr"),
    ("France", "importer", "plant-health import controls/interceptions", "free", "no",
     "SIVEP/DGAL + EU EUROPHYT/TRACES", "https://agrinfo.eu/book-of-reports/",
     "by commodity/origin", "", _TODAY, "no national interception dataset; EUROPHYT is the free fallback"),
    ("France", "exporter", "domestic blueberry area/production (myrtilles)", "free", "no",
     "Agreste (SSP) + FranceAgriMer", "https://agreste.agriculture.gouv.fr/",
     "national/regional, area+production", "", "",
     "myrtilles within 'petits fruits rouges'; small; 403 from sandbox"),

    # ---- China (#6 importer 2023; huge domestic producer) ----
    ("China", "importer", "national customs trade detail (HS8)", "free", "no",
     "GACC China Customs Statistics", "http://stats.customs.gov.cn/",
     "monthly, HS8 x partner", "", "",
     "Chinese-language, registration+CAPTCHA; English mirror aggregate; yearbook paid"),
    ("China", "importer", "registered overseas producers (phyto import access)", "free", "no",
     "GACC CIFER", "https://ciferquery.singlewindow.cn", "registered enterprise by product/country",
     "", _TODAY, "public JS query (verified reachable) but no clean machine API found from sandbox "
     "-- needs JS/network inspection; blueberry orchards live in per-country protocol annexes"),
    ("China", "exporter", "domestic blueberry area/production", "none", "na",
     "NBS (no blueberry line); China Blueberry Branch (industry)", "https://data.stats.gov.cn/english/",
     "national/province, not broken out", "", "",
     "NBS folds blueberry into general fruit; industry ~73k ha 2024 via USDA"),
    ("China", "importer", "production/import forecast", "free", "no",
     "USDA-FAS GAIN (Beijing ATO)", "https://www.fas.usda.gov/data/china-fresh-deciduous-fruit-annual-5",
     "season-ahead", "", "", "dedicated China Blueberry Annual (voluntary) + Fresh Deciduous Annual; 403 to bots"),

    # ---- Hong Kong (#4-ish re-export hub 2023) ----
    ("Hong Kong", "both", "customs trade detail (import / domestic-export / re-export)", "free", "no",
     "HK Census & Statistics Dept -- Trade IDDS", "https://tradeidds.censtatd.gov.hk",
     "monthly, HKHS 8-digit x partner; re-exports split", "", "",
     "the only clean re-export split in the catalogue; HS 0810.40; 403 from sandbox"),
    ("Hong Kong", "importer", "plant import control", "free", "na",
     "AFCD plant import licence", "https://www.afcd.gov.hk/english/quarantine/qua_plants/qua_plants_pq/qua_plants_pq_imp/qua_plants_pq_imp.html",
     "per-consignment licence + phyto cert", "", _TODAY,
     "no orchard whitelist; AFCD issues re-export phyto certs (hub role)"),

    # ---- Switzerland (#7 importer 2023) ----
    ("Switzerland", "importer", "national customs trade detail (8-digit Zolltarif)", "free", "no",
     "Swiss-Impex (BAZG/FOCBS)", "https://www.bazg.admin.ch/en/foreign-trade-statistics",
     "monthly back to 1988, by partner", "", _TODAY,
     "free dashboard (Dec 2025); custom extracts paid; HS 0810.40"),
    ("Switzerland", "importer", "plant-health import requirements", "free", "na",
     "FOAG/BLW plant protection", "https://www.blw.admin.ch/en/importing-plants",
     "import rules by genus/origin", "", _TODAY,
     "phyto cert required non-EU; no blueberry approved-country list"),

    # ---- South Korea (#10 importer 2023; ~3,300 ha domestic) ----
    ("South Korea", "importer", "national customs trade detail (HSK 10-digit)", "free", "no",
     "KITA K-Stat (English) / KCS / KATI", "https://kita.org/kStat/byCount_AllCount.do",
     "monthly, HSK10 x partner", "", _TODAY, "K-Stat is the English route; KCS/KATI thinner in English"),
    ("South Korea", "importer", "phyto import access (positive-list/PRA)", "free", "no",
     "APQA (Animal & Plant Quarantine Agency)", "https://www.qia.go.kr", "approved origins per PRA",
     "", "", "positive-list; blueberry eligibility per-origin; Korean-only DB; 403 from sandbox"),
    ("South Korea", "exporter", "domestic blueberry area/production", "free", "no",
     "KOSIS (Statistics Korea)", "https://kosis.kr/eng/", "crop area/production", "", "",
     "~3,300 ha 2022; import-dependent; 403 from sandbox"),

    # ---- Japan (#15 importer 2023) ----
    ("Japan", "importer", "national customs trade detail (HS 9-digit)", "free", "no",
     "Japan Customs Trade Statistics + e-Stat", "https://www.customs.go.jp/toukei/srch/indexe.htm",
     "monthly, HS9 x partner; English", "", _TODAY, "e-Stat API mirror; HS 0810.40"),
    ("Japan", "importer", "phyto import requirements", "free", "na",
     "MAFF Plant Protection Station", "https://www.maff.go.jp/pps/j/introduction/english.html",
     "import conditions by origin", "", _TODAY, "phyto cert + inspection; condition DB partly JP-only"),

    # ---- Belgium (re-export hub) ----
    ("Belgium", "both", "national customs trade detail (CN8)", "free", "no",
     "NBB.Stat (National Bank of Belgium)", "https://stat.nbb.be",
     "monthly, CN8; national+community concept", "", "",
     "trade stats at NBB, NOT StatBel; mainly re-export; 403 from sandbox"),
    ("Belgium", "both", "plant export/re-export certification (phyto)", "free", "na",
     "FASFC/FAVV-AFSCA", "https://www.fasfc.be", "operator-registered certificates", "", _TODAY,
     "designated NPPO; issues re-export phyto certs"),

    # ---- Portugal (EU; real producer/exporter) ----
    ("Portugal", "exporter", "national customs trade detail (CN)", "free", "no",
     "INE Portugal + Eurostat COMEXT", "https://www.ine.pt", "CN-level intl trade in goods", "", _TODAY, ""),
    ("Portugal", "exporter", "domestic blueberry area/production (mirtilo)", "free", "no",
     "INE Portugal -- agricultural production", "https://www.ine.pt", "national/regional, ha + t",
     "2013->now", _TODAY, "fast-growing: 534 ha (2013) -> ~2,627 ha, ~21,000 t (2023)"),
    ("Portugal", "exporter", "phyto export register", "free", "na",
     "DGAV", "https://www.dgav.pt", "operator phyto-register", "", _TODAY, "national NPPO"),

    # ---- Italy (importer; some production) ----
    ("Italy", "importer", "national customs trade detail (CN)", "free", "no",
     "ISTAT Foreign Trade warehouse + Eurostat COMEXT", "https://esploradati.istat.it/coeweb/databrowser/#/en",
     "Intrastat+Extrastat, CN-level", "", _TODAY, "Coeweb retired Sep 2025 -> esploradati warehouse"),
    ("Italy", "exporter", "domestic blueberry area/production", "none", "na",
     "ISTAT ag DB (no confirmed blueberry line); ItalianBerry (industry)", "https://esploradati.istat.it/",
     "~1,390 ha (industry est.)", "", "", "official blueberry series not confirmed; industry-sourced"),

    # ---- Austria (importer) ----
    ("Austria", "importer", "national customs trade detail (CN8)", "free", "no",
     "Statistics Austria STATcube + Eurostat COMEXT", "https://www.statistik.at/en/databases/statcube-statistical-database",
     "Intrastat+Extrastat", "", "", "Guest Access limited; full CN8 depth paid; 403 from sandbox"),
    ("Austria", "importer", "plant-health (phyto) authority", "free", "na",
     "BAES (Bundesamt fuer Ernaehrungssicherheit)", "https://www.baes.gv.at/en/admission/phytosanitary-service",
     "NPPO", "", "", "designated NPPO; 403 from sandbox"),

    # ---- Serbia (non-EU exporter; NOT in COMEXT) ----
    ("Serbia", "exporter", "national customs trade detail (HS 10-digit)", "free", "no",
     "SORS External Trade + Customs Administration", "https://data.stat.gov.rs",
     "monthly preliminary + annual final, HS10", "", _TODAY,
     "not in COMEXT (non-EU); HS 0810 isolable"),
    ("Serbia", "exporter", "domestic blueberry area/production (borovnica)", "free", "no",
     "SORS Agriculture (annual crop survey)", "https://www.stat.gov.rs/en-us/oblasti/poljoprivreda-sumarstvo-i-ribarstvo/",
     "~2,500 ha; EUROSTAT-harmonised", "", "", "blueberry line not confirmed in public browser; verify in ag DB"),
    ("Serbia", "exporter", "phyto export authority", "free", "na",
     "Plant Protection Directorate (Uprava za zastitu bilja)", "https://uzb.minpolj.gov.rs",
     "export phyto certs", "", _TODAY, "national NPPO"),
    ("Serbia", "exporter", "production/export forecast", "none", "na",
     "USDA-FAS GAIN (Belgrade)", "https://www.fas.usda.gov/regions/serbia", "n/a", "", "",
     "no Serbia blueberry GAIN; covered in EU Fresh Deciduous Annual if at all"),
]


# ---- Phase 2c: tail importer markets in the 95% set (<1% each) ----
# Completes "every country in the 95% set". EU members' CN8 trade is already wired via
# the global Eurostat COMEXT row, so here it's the national office + the import-side NPPO.
# verified_date left blank -- research-confirmed URLs, to be probed on the runner.
_SEED_PHASE2C: list[tuple] = [
    # ---- non-EU (re-distribution markets / hubs) ----
    ("Singapore", "both", "national customs trade detail (HS, re-export)", "free", "no",
     "SingStat Table Builder + Singapore Customs", "https://tablebuilder.singstat.gov.sg/",
     "HS-level merchandise trade, monthly", "", "", "re-distribution hub; free interactive"),
    ("Singapore", "importer", "plant-health import authority", "free", "na",
     "NParks Animal & Veterinary Service (AVS)", "https://www.nparks.gov.sg/services/import-plant-plant-products",
     "import permit + phyto", "", "", ""),
    ("Norway", "importer", "national customs trade detail (HS)", "free", "no",
     "Statistics Norway (SSB) StatBank 08799", "https://www.ssb.no/en/statbank/list/muh",
     "HS x partner, monthly", "", "", ""),
    ("Norway", "importer", "plant-health import authority", "free", "na",
     "Mattilsynet (Norwegian Food Safety Authority)", "https://www.mattilsynet.no/en/plants",
     "import rules", "", "", ""),
    ("Ireland", "importer", "national customs trade detail (HS)", "free", "no",
     "CSO Ireland / Eurostat COMEXT", "https://www.cso.ie/en/databases/",
     "HS x partner, monthly", "", "", "entered the 95% importer target set on 2024 data"),
    ("Ireland", "importer", "plant-health import authority", "free", "na",
     "DAFM (Dept of Agriculture, Food & the Marine)", "https://www.gov.ie/en/organisation/department-of-agriculture-food-and-the-marine/",
     "import rules", "", "", ""),
    ("Australia", "importer", "national customs trade detail (HS)", "free", "no",
     "ABS International Trade", "https://www.abs.gov.au/statistics/economy/international-trade",
     "HS x partner, monthly", "", "", "entered the 95% importer target set on 2024 data; minor blueberry importer"),
    ("Australia", "importer", "plant-health import authority", "free", "na",
     "DAFF Biosecurity (BICON)", "https://bicon.agriculture.gov.au/",
     "import conditions", "", "", "strict biosecurity; fresh blueberry access limited"),
    ("United Arab Emirates", "both", "national customs trade detail (HS, re-export)", "free", "no",
     "FCSC UAE.Stat International Trade", "https://uaestat.fcsc.gov.ae/",
     "HS-level, by partner", "", "", "re-export hub; JS portal (browser/runner)"),
    ("United Arab Emirates", "importer", "plant-health import authority", "free", "na",
     "MOCCAE import permit", "https://www.moccae.gov.ae/en/services/export-import-services/import-permit.aspx",
     "import permit", "", "", ""),
    # ---- EU members (CN8 trade already wired via the global COMEXT row) ----
    ("Czechia", "importer", "national customs trade detail (CN8)", "free", "no",
     "Eurostat COMEXT + Czech Statistical Office (CZSO)", "https://www.czso.cz/csu/czso/databases-registers",
     "CN8 via COMEXT (wired); national DB", "", "", "EU -- CN8 trade covered by the wired COMEXT row"),
    ("Czechia", "importer", "plant-health import authority", "free", "na",
     "UKZUZ", "https://ukzuz.gov.cz/public/portal/ukzuz/en/import-export/index-1", "NPPO", "", "", ""),
    ("Denmark", "importer", "national customs trade detail (CN8)", "free", "no",
     "Eurostat COMEXT + Statistics Denmark (DST)", "https://www.statbank.dk/",
     "CN8 via COMEXT (wired); national DB", "", "", "EU -- COMEXT-covered"),
    ("Denmark", "importer", "plant-health import authority", "free", "na",
     "Danish Agricultural Agency (Landbrugsstyrelsen)", "https://en.lbst.dk/", "NPPO", "", "", ""),
    ("Romania", "importer", "national customs trade detail (CN8)", "free", "no",
     "Eurostat COMEXT + INSSE TEMPO-Online", "https://insse.ro/cms/en",
     "CN8 via COMEXT (wired); national DB", "", "", "EU -- COMEXT-covered"),
    ("Romania", "importer", "plant-health import authority", "free", "na",
     "National Phytosanitary Authority (ANF)", "https://anfdf.ro/", "NPPO", "", "", ""),
    ("Sweden", "importer", "national customs trade detail (CN8)", "free", "no",
     "Eurostat COMEXT + Statistics Sweden (SCB)",
     "https://www.scb.se/en/finding-statistics/statistics-by-subject-area/business-activities-and-foreign-trade/foreign-trade/foreign-trade-in-goods/",
     "CN8 via COMEXT (wired); national DB", "", "", "EU -- COMEXT-covered"),
    ("Sweden", "importer", "plant-health import authority", "free", "na",
     "Swedish Board of Agriculture (Jordbruksverket)",
     "https://jordbruksverket.se/languages/english/swedish-board-of-agriculture/plants", "NPPO", "", "", ""),
    ("Lithuania", "importer", "national customs trade detail (CN8)", "free", "no",
     "Eurostat COMEXT + Statistics Lithuania (OSP)", "https://osp.stat.gov.lt/en",
     "CN8 via COMEXT (wired); national DB", "", "", "EU -- COMEXT-covered"),
    ("Lithuania", "importer", "plant-health import authority", "free", "na",
     "State Plant Service (VATZUM)", "https://vatzum.lrv.lt/en/", "NPPO", "", "", ""),
    ("Slovakia", "importer", "national customs trade detail (CN8)", "free", "no",
     "Eurostat COMEXT + Statistical Office (SUSR DATAcube)", "https://datacube.statistics.sk/",
     "CN8 via COMEXT (wired); national DB", "", "", "EU -- COMEXT-covered"),
    ("Slovakia", "importer", "plant-health import authority", "free", "na",
     "UKSUP", "https://www.uksup.sk/en", "NPPO", "", "", ""),
]


def _records() -> list[dict]:
    rows = []
    for t in _SEED + _SEED_PHASE2 + _SEED_PHASE2B + _SEED_PHASE2C:
        rec = {"commodity": _COMMODITY, "hs_code": _HS}
        rec.update(dict(zip(_FIELDS, t)))
        rows.append(rec)
    return rows


def seed() -> pd.DataFrame:
    """(Re)build the registry from the transcribed baselines and write the CSV."""
    df = pd.DataFrame(_records(), columns=schema.COLUMNS)
    issues = schema.validate(df)
    if issues:
        raise ValueError("seed violates schema: " + "; ".join(issues))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False)
    return df


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return schema.empty()
    return pd.read_csv(CACHE, keep_default_na=False)


def gaps(access: str | None = None, wired: str | None = None) -> pd.DataFrame:
    """Filter the registry. `access='paid'` = the paid ceiling; `access='none'` =
    structural gaps; `access='free', wired='no'` = the free-but-unwired headroom."""
    df = load()
    if access is not None:
        df = df[df["access"] == access]
    if wired is not None:
        df = df[df["wired"] == wired]
    return df.reset_index(drop=True)


def coverage_buckets() -> dict:
    """Honest split of what 'free but unwired' actually means, so the count isn't read
    as untapped datasets. A free data-point is one of:
      held         -- free + wired (we hold it)
      base_covered -- unwired, but its AXIS is already measured globally by a wired base
                      layer (national customs -> Comtrade/COMEXT flow; national area ->
                      FAOSTAT; weather -> NASA POWER). Finer granularity, not new signal.
      headroom     -- genuinely unwired *new* signal (mostly fragile/marginal: demand
                      scrapes, origin daily/weekly, phyto rosters, border detail)
      info_only    -- wired='na': an info/process page, not a dataset to wire
    plus the paid ceiling and structural-gap (none) totals.
    """
    df = load()
    dp = df["data_point"].str.lower()
    free = df["access"] == "free"
    held = free & df["wired"].isin(["yes", "derived"])
    info = free & (df["wired"] == "na")
    unwired = free & ~held & ~info
    is_customs = dp.str.contains("customs trade detail", na=False)
    is_area = (dp.str.contains("area", na=False) | dp.str.contains("production", na=False)) \
        & ~dp.str.contains("forecast", na=False)
    is_cond = dp.str.contains("weather|ndvi|drought|frost", regex=True, na=False)
    base = unwired & (is_customs | is_area | is_cond)
    return {
        "held": int(held.sum()),
        "base_covered": int((base).sum()),
        "headroom": int((unwired & ~base).sum()),
        "info_only": int(info.sum()),
        "paid": int((df["access"] == "paid").sum()),
        "none": int((df["access"] == "none").sum()),
    }


def coverage() -> pd.DataFrame:
    """access x wired counts -- the one-glance shape of the catalogue."""
    df = load()
    if df.empty:
        return df
    return (df.groupby(["access", "wired"]).size().rename("n")
            .reset_index().sort_values(["access", "wired"]).reset_index(drop=True))


if __name__ == "__main__":                             # python -m atlas.registry
    df = seed()
    print(f"seeded {len(df)} rows -> {CACHE}  (catalogue date {_dt.date.today()})")
    print("\ncoverage (access x wired):")
    print(coverage().to_string(index=False))
