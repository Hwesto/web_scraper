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

# -- Target commodity --
# CN8 08104050 = "Fresh fruit of species Vaccinium macrocarpum and Vaccinium
# corymbosum" i.e. cultivated blueberry (corymbosum) + large cranberry
# (macrocarpum). This is the commercial blueberry line. NB the spec's original
# 08104010 is lingonberry/cowberry -- wrong code.
COMMODITY_ID = 8104050
COMMODITY_CN8 = "08104050"

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
