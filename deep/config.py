"""Central configuration for the UK blueberry hidden-flow nowcast.

Every constant here was verified against the live HMRC OData API on 2026-06-16,
not assumed. See the inline notes for what each value means and why it is set.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

# -- Paths --
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
VINTAGE_DIR = DATA_DIR / "vintages"          # append-only, gitignored
VINTAGE_DIR.mkdir(parents=True, exist_ok=True)

# ====================== FRUIT — the single retarget point ======================
# Change THIS block to point the whole board/atlas at another fruit. Everything
# downstream (HMRC, Comtrade, FAOSTAT, the masthead, the in-season strip, the
# production caveat) reads from here, so a new fruit is one edit, not fifteen.
FRUIT_NAME = "Blueberry"          # masthead title: "Britain's {FRUIT_NAME} Board"
FRUIT_EMOJI = "🫐"                # optional eyebrow glyph; set "" to omit
HS6 = "081040"                    # UN Comtrade HS-6 (global trade + production trade)
# HMRC UK CN8 08104050 = "Fresh Vaccinium macrocarpum & corymbosum" = cultivated
# blueberry + large cranberry (the commercial blueberry line; 08104010 is the
# wrong code = lingonberry/cowberry).
COMMODITY_ID = 8104050            # HMRC numeric CommodityId
COMMODITY_CN8 = "08104050"
FAOSTAT_ITEM = "Blueberries"      # FAOSTAT QCL production item name
ODEPA_HS_PREFIX = "081040"        # Chile ODEPA fresh-fruit prefix (deep nowcast)
# Major UK-supply origins in volume — the in-season per-origin landed price strip.
INSEASON_ORIGINS = ["Chile", "Peru", "Morocco", "Spain", "Netherlands", "South Africa"]
# Production the FREE sources miss — documented per-country overrides, NOT fabricated.
# {country: (tonnes, year, source)}. Empty {} for fruits FAOSTAT covers fully — then
# the gap note below is unused and the consumption section needs no caveat.
PRODUCTION_OVERRIDES = {"China": (525_000, 2023, "Produce Report / IBO (2023 est.)")}
# World-map caveat shown only when an override exists (commodity-specific narrative).
PRODUCTION_GAP_NOTE = (
    "† <b>China</b> looks small here but grows most of what it eats — reported (IBO) "
    "as the world's largest producer, yet it reports no output to FAOSTAT and imports "
    "little, so <b>no free dataset captures its true scale</b>. Netherlands, Belgium "
    "&amp; Hong Kong are re-export hubs (high trade, low home demand).")
# ===============================================================================

# -- HMRC OData API --
HMRC_API_BASE = "https://api.uktradeinfo.com"
# Allowed OData ops are restricted server-side: $filter, $select, $top, $skip
# and @odata.nextLink paging work; $orderby is rejected. Page by MonthId range.
HMRC_PAGE_DELAY_S = 1.5      # politeness between paged requests
HMRC_MAX_RETRIES = 4        # network/rate-limit retries, exponential backoff

# FlowTypeId (verified): 1=EU Imports, 2=EU Exports, 3=Non-EU Imports,
# 4=Non-EU Exports. The EU/non-EU split is a *collection-method* seam (Intrastat
# vs customs declarations) -- the post-Brexit consistency caveat lives here.
FLOW_EU_IMPORTS = 1
FLOW_NONEU_IMPORTS = 3
FLOW_EU_EXPORTS = 2      # dispatches (Intrastat)
FLOW_NONEU_EXPORTS = 4   # exports (customs) -- together: UK re-exports of blueberries

# CountryId -> (name, alpha2, flow_type). Verified against /Country.
# The stated target is the opaque EU/Morocco flow; Peru/Chile/Portugal/NL are
# carried for seasonal context (counter-season deep-sea supply, EU neighbours).
ORIGINS = {
    11:  {"name": "Spain",       "alpha2": "ES", "flow": FLOW_EU_IMPORTS,    "group": "target"},
    204: {"name": "Morocco",     "alpha2": "MA", "flow": FLOW_NONEU_IMPORTS, "group": "target"},
    10:  {"name": "Portugal",    "alpha2": "PT", "flow": FLOW_EU_IMPORTS,    "group": "context"},
    3:   {"name": "Netherlands", "alpha2": "NL", "flow": FLOW_EU_IMPORTS,    "group": "context"},
    504: {"name": "Peru",        "alpha2": "PE", "flow": FLOW_NONEU_IMPORTS, "group": "counter_season"},
    512: {"name": "Chile",       "alpha2": "CL", "flow": FLOW_NONEU_IMPORTS, "group": "counter_season"},
}

# Earliest MonthId to attempt. The consistent *origin-level* series is post-Brexit
# only (customs declarations carry origin from 2022). We pull history back to 2018
# for trend/seasonal context but treat <202201 as lower-trust for the target flow.
HISTORY_START_MONTH = 201801
CONSISTENT_ORIGIN_MONTH = 202201

# -- Unit conventions --
# Model lives in VOLUME space so temporal aggregation stays linear. HMRC NetMass
# is in kilograms; we convert to tonnes/week-or-month everywhere downstream.
KG_PER_TONNE = 1000.0

# -- DEFRA weekly wholesale price (nowcast proxy, demand-confounded) --
DEFRA_PRICE_PAGE = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "wholesale-fruit-and-vegetable-prices-weekly-average"
)

# -- Satellite NDVI (free, no-auth) via NASA/ORNL MODIS MOD13Q1 (250m, 16-day) --
# Berry-growing centroids per origin. NDVI here is a crude regional proxy: Huelva
# and Larache berries grow under poly/macro-tunnels that mask the canopy, and a
# few-km box mixes in other land cover -- so expect a weak, confounded signal.
MODIS_PRODUCT = "MOD13Q1"
MODIS_BAND = "250m_16_days_NDVI"
NDVI_REGIONS = {
    "Spain":   {"lat": 37.25, "lon": -6.95, "label": "Huelva"},
    "Morocco": {"lat": 35.18, "lon": -6.15, "label": "Larache"},
    "Chile":   {"lat": -36.9, "lon": -72.2, "label": "Ñuble/Bío Bío"},
}

# -- Rejected alt-data methods (kept so the rationale is not re-litigated) --
# Each is a real technique; each fails a hard constraint we already set.
REJECTED_SIGNALS = {
    "tasking_satellites":   "breaks free-only budget (Maxar/Planet tasking is paid)",
    "thermal_reefer_count": "free TIR is 70-100m (ECOSTRESS/Landsat); cannot resolve ~12m containers",
    "packhouse_optical":    "free optical (Sentinel-2 10m) too coarse; sub-m is paid + cloud-gated",
    "freight_load_boards":  "Timocom/Teleroute are account-gated and prohibit scraping (ToS)",
    "container_enumeration": "Destin8/Portbase are credential-gated; enumerating others' "
                             "container numbers risks UK Computer Misuse Act 1990",
    "ais_deep_sea":         "historical/vintage AIS is paid; target flow is road not deep-sea",
    "kantar_scan":          "commercial/paid; only headline market share is public",
}

TODAY = _dt.date.today
