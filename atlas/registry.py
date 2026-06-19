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
    ("Peru", "exporter", "named exporter", "free", "no",
     "Agrodata / SUNAT", "agrodataperu.com", "named", "", "",
     "partly free (Camposol/Hortifrut/Agrovision/Danper); BoL detail is paid"),
    ("Peru", "exporter", "cultivar per shipment", "none", "na",
     "", "", "", "", "", "SUNAT customs does not carry cultivar (unlike Chile DUS)"),
    ("Peru", "exporter", "season export progress, by week", "free", "no",
     "ProArandanos", "proarandanos.org", "weekly campaign volumes", "", "",
     "no structured feed -- 403/press/PDF only; fragile scrape"),
    ("Peru", "exporter", "area / production / exports + forecasts", "free", "yes",
     "USDA-FAS Blueberry Annual (Lima)", "apps.fas.usda.gov/newgainapi", "PSD table, annual",
     "2022/23->2026/27", _TODAY, "the Catastro substitute; manual annual bump"),
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
     "2012->2025", _TODAY, "the free global base layer; every cell from one source"),
    ("*", "global", "FX USD/GBP (and crosses)", "free", "yes",
     "Frankfurter / ECB", "api.frankfurter.app", "daily", "daily", _TODAY,
     "replaces notional 0.79"),
    ("*", "global", "tariffs / duties into UK", "free", "no",
     "UK Trade Tariff", "trade-tariff.service.gov.uk", "per origin", "", "",
     "fresh blueberries 0% under UK-Chile / UK-Andean; confirm & note"),
    ("*", "global", "production / export forecasts", "free", "no",
     "USDA FAS (free); iQonsulting / Frutas de Chile (paid)", "apps.fas.usda.gov",
     "season-ahead", "", "", "Peru forecast wired; Chile forecast free-partial/paid"),
]


def _records() -> list[dict]:
    rows = []
    for t in _SEED:
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
