"""Growing-region weather/climate from NASA POWER -- the condition base layer.

The "is the crop in good conditions" axis, globally, from one keyless source: NASA
POWER serves monthly mean/min/max temperature (C) and precipitation (mm/day) for any
lat/lon (AG community), back decades. We sample the centroid of each major blueberry
growing region per origin, so frost risk (T2M_MIN), heat and rainfall are tracked for
the whole producing world at once -- the same one-source-per-axis play as Comtrade
(trade) and FAOSTAT (production). Finer satellite NDVI (`nowcast` MODIS/Sentinel-2)
layers on top selectively.

Committed to `data/atlas/weather_regions.csv` (origin, region, lat, lon, year, month,
t2m, tmin, tmax, precip_mm_day). `climatology()` gives a region's monthly profile.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "weather_regions.csv"
_API = ("https://power.larc.nasa.gov/api/temporal/monthly/point"
        "?parameters=T2M,T2M_MIN,T2M_MAX,PRECTOTCORR&community=AG"
        "&longitude={lon}&latitude={lat}&start={start}&end={end}&format=JSON")
_PARAM = {"T2M": "t2m", "T2M_MIN": "tmin", "T2M_MAX": "tmax", "PRECTOTCORR": "precip_mm_day"}
_COLS = ["origin", "region", "lat", "lon", "year", "month",
         "t2m", "tmin", "tmax", "precip_mm_day"]

# Centroid of each major blueberry growing region. One per top origin (USA spans
# climates, so three). Extend as the atlas widens.
REGIONS = [
    {"origin": "Peru", "region": "La Libertad", "lat": -8.1, "lon": -79.0},
    {"origin": "Chile", "region": "Nuble/Biobio", "lat": -36.9, "lon": -72.2},
    {"origin": "Mexico", "region": "Jalisco", "lat": 20.5, "lon": -103.4},
    {"origin": "Mexico", "region": "Michoacan (Los Reyes)", "lat": 19.6, "lon": -102.5},
    {"origin": "Spain", "region": "Huelva", "lat": 37.25, "lon": -6.95},
    {"origin": "Morocco", "region": "Larache/Loukkos", "lat": 35.18, "lon": -6.15},
    {"origin": "USA", "region": "Oregon (Willamette)", "lat": 44.5, "lon": -123.2},
    {"origin": "USA", "region": "Georgia", "lat": 31.5, "lon": -82.3},
    {"origin": "USA", "region": "Michigan", "lat": 42.3, "lon": -86.2},
    {"origin": "South Africa", "region": "Western Cape", "lat": -33.6, "lon": 19.0},
    {"origin": "Poland", "region": "Mazovia", "lat": 52.0, "lon": 21.0},
    {"origin": "Portugal", "region": "Alentejo (Odemira)", "lat": 37.6, "lon": -8.6},
    {"origin": "Argentina", "region": "Tucuman/Concordia", "lat": -31.4, "lon": -58.0},
    {"origin": "China", "region": "Yunnan", "lat": 25.0, "lon": 102.7},
]


def _fetch(lat: float, lon: float, start: int, end: int, retries: int = 4) -> dict:
    url = _API.format(lat=lat, lon=lon, start=start, end=end)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["properties"]["parameter"]
        except Exception as e:                         # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"NASA POWER fetch failed ({lat},{lon}): {last}")


def _parse(param: dict, region: dict) -> list[dict]:
    """POWER parameter block -> monthly rows for one region (offline-testable).
    POWER keys are YYYYMM with a YYYY13 annual rollup we skip; -999 == fill/missing."""
    months: dict[int, dict] = {}
    for pkey, col in _PARAM.items():
        for ym, val in (param.get(pkey) or {}).items():
            if ym.endswith("13"):                      # annual rollup, skip
                continue
            if val is None or float(val) <= -999:       # POWER missing-value sentinel
                continue
            months.setdefault(int(ym), {})[col] = round(float(val), 2)
    rows = []
    for ym, vals in sorted(months.items()):
        rows.append({"origin": region["origin"], "region": region["region"],
                     "lat": region["lat"], "lon": region["lon"],
                     "year": ym // 100, "month": ym % 100, **vals})
    return rows


def refresh(start: int, end: int, regions: list[dict] | None = None) -> pd.DataFrame:
    """Fetch monthly weather for each growing region over [start,end]; (re)write cache."""
    regions = regions or REGIONS
    rows = []
    for reg in regions:
        rows.extend(_parse(_fetch(reg["lat"], reg["lon"], start, end), reg))
        time.sleep(0.3)
    fresh = pd.DataFrame(rows, columns=_COLS)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.sort_values(["origin", "region", "year", "month"]).to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def climatology(origin: str | None = None, region: str | None = None) -> pd.DataFrame:
    """Monthly climate normals (mean across cached years) per region -- the seasonal
    profile: mean temp, frost-proxy min temp, rainfall."""
    df = load()
    if df.empty:
        return df
    if origin is not None:
        df = df[df["origin"] == origin]
    if region is not None:
        df = df[df["region"] == region]
    g = (df.groupby(["origin", "region", "month"])
           .agg(t2m=("t2m", "mean"), tmin=("tmin", "mean"),
                tmax=("tmax", "mean"), precip_mm_day=("precip_mm_day", "mean"))
           .round(2).reset_index())
    return g.sort_values(["origin", "region", "month"]).reset_index(drop=True)


if __name__ == "__main__":                             # python -m atlas.nasa_power
    this = _dt.date.today().year
    df = refresh(this - 6, this - 1)                    # ~6 yrs for robust normals
    print(f"cached {len(df)} region-months -> {CACHE}")
    clim = climatology()
    # coldest month per region (frost-risk lens via mean min temp)
    idx = clim.groupby(["origin", "region"])["tmin"].idxmin()
    cold = clim.loc[idx, ["origin", "region", "month", "tmin"]]
    print("\ncoldest month (mean T2M_MIN) by growing region:")
    print(cold.to_string(index=False))
