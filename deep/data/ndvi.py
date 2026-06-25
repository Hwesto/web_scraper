"""Satellite NDVI ingest -- the only free signal that is structurally LEADING.

Pulls regional MODIS NDVI (MOD13Q1, 250m, 16-day) over each origin's berry-
growing centroid from the free, no-auth NASA/ORNL subset API, averages valid
pixels in a small box, and returns a tidy 16-day series per origin.

Rationale and caveat: crop greenness leads harvest/shipment by weeks, so unlike
price NDVI *can* lead import volume -- IF it tracks the crop. Huelva/Larache
berries grow under poly-tunnels that mask the canopy, and a few-km box mixes in
other land cover, so the signal is expected to be weak and confounded. Whether
it actually leads volume is an empirical question the diagnostic answers.
"""
from __future__ import annotations

import datetime as _dt
import time

import numpy as np
import requests

from .base import SignalSource
from ..config import MODIS_BAND, MODIS_PRODUCT, NDVI_REGIONS

_BASE = "https://modis.ornl.gov/rst/api/v1"
_HEADERS = {"Accept": "application/json", "User-Agent": "uk-blueberry-nowcast/0.1"}
_FILL_FLOOR = -2000          # MOD13Q1 fill is -3000; valid NDVI*1e4 in [-2000,10000]
_SCALE = 1e-4
_DOYS = list(range(1, 366, 16))   # MOD13Q1 composite start days (23/year)
_MAX_DATES = 10                   # API caps each subset request at 10 composites


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _fetch_point(lat: float, lon: float, year: int, km: int = 3) -> list[tuple[str, float]]:
    out = []
    for grp in _chunks(_DOYS, _MAX_DATES):
        url = (f"{_BASE}/{MODIS_PRODUCT}/subset?latitude={lat}&longitude={lon}"
               f"&band={MODIS_BAND}&startDate=A{year}{grp[0]:03d}&endDate=A{year}{grp[-1]:03d}"
               f"&kmAboveBelow={km}&kmLeftRight={km}")
        payload = None
        for attempt in range(4):                      # ORNL throttles bulk runs
            try:
                r = requests.get(url, headers=_HEADERS, timeout=40)
                if r.status_code == 200:
                    payload = r.json()
                    break
            except Exception:                          # noqa: BLE001 -- retry transient
                pass
            time.sleep(1.5 * (attempt + 1))
        if not isinstance(payload, dict):
            continue
        for row in payload.get("subset", []):
            vals = np.array(row["data"], float)
            vals = vals[vals > _FILL_FLOOR]
            if vals.size:
                out.append((row["calendar_date"], float(vals.mean()) * _SCALE))
        time.sleep(0.5)                                # polite between composites
    return out


class SatelliteNdvi(SignalSource):
    """Regional NDVI per origin growing region (16-day composites)."""

    series = "satellite_ndvi"
    freq = "W"          # 16-day composites; treated as irregular weekly-ish
    unit = "ndvi"

    def __init__(self, year_start: int = 2018, year_end: int | None = None):
        self.year_start = year_start
        self.year_end = year_end or _dt.date.today().year

    def fetch(self, vintage_date: _dt.date | None = None) -> "pd.DataFrame":  # noqa: F821
        vintage_date = vintage_date or _dt.date.today()
        records = []
        for origin, geo in NDVI_REGIONS.items():
            for year in range(self.year_start, self.year_end + 1):
                for cal_date, ndvi in _fetch_point(geo["lat"], geo["lon"], year):
                    records.append({
                        "series": self.series,
                        "ref_period": cal_date,
                        "freq": self.freq,
                        "key": origin,
                        "value": ndvi,
                        "unit": self.unit,
                    })
        return self._tidy(records, vintage_date)


if __name__ == "__main__":
    df = SatelliteNdvi(year_start=2023).fetch()
    print(f"rows: {len(df)}  origins: {sorted(df['key'].unique())}")
    print(df.groupby("key")["value"].agg(["count", "mean"]).round(3).to_string())
