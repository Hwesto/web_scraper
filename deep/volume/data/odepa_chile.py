"""Chile -> UK fresh blueberry exports (origin customs) via ODEPA open data.

ODEPA (Chile's agriculture ministry) republishes Servicio Nacional de Aduanas
export records as yearly CKAN datastore resources: monthly volume (net kg) by
product x destination x region. We pull fresh-blueberry codes (081040*) with
destination 'Reino Unido' and sum to monthly tonnes per year.

Why this matters (verified): origin export LEADS HMRC import by the deep-sea
transit time (~3-5 weeks), and is an independent measure of the same flow -- so
it is both a 'shipment'-tier series and the two-sided cross-check (spec section
6). It is MONTHLY: the daily DUS feed lives on datos.gob.cl, which is not
reachable here, so weekly shape still comes from the model.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import requests

from ...data.base import SignalSource
from ...config import KG_PER_TONNE

_CKAN = "https://datos.odepa.gob.cl/api/3/action"
_PACKAGE = "comercio-exterior"
_HEADERS = {"User-Agent": "Mozilla/5.0 (uk-blueberry-nowcast/0.1)"}
_DEST = "Reino Unido"
_FRESH_PREFIX = "081040"     # fresh Vaccinium (frozen would be 0811 -- excluded)


def _to_float(raw) -> float:
    """Parse Chilean number format '1.234.567,89' -> 1234567.89."""
    if raw in (None, ""):
        return 0.0
    return float(str(raw).replace(".", "").replace(",", "."))


def _resource_ids() -> dict[int, str]:
    """Map year -> datastore resource id from the package metadata."""
    pkg = requests.get(f"{_CKAN}/package_show", params={"id": _PACKAGE},
                       headers=_HEADERS, timeout=40).json()
    out = {}
    for res in pkg["result"]["resources"]:
        name = res.get("name", "")
        if "Exportaciones del año" in name and res.get("datastore_active"):
            try:
                out[int(name.split()[-1])] = res["id"]
            except ValueError:
                continue
    return out


def _fetch_year(resource_id: str) -> list[tuple[int, float]]:
    """Return [(month, net_kg)] for fresh blueberries to the UK, one year."""
    rows, offset = [], 0
    while True:
        payload = requests.get(
            f"{_CKAN}/datastore_search",
            params={"resource_id": resource_id,
                    "filters": '{"Pais destino":"%s"}' % _DEST,
                    "limit": 1000, "offset": offset},
            headers=_HEADERS, timeout=60,
        ).json()["result"]["records"]
        for r in payload:
            if str(r["Codigo producto"]).startswith(_FRESH_PREFIX):
                rows.append((int(r["Mes"]), _to_float(r["Volumen"])))
        if len(payload) < 1000:
            break
        offset += 1000
    return rows


class OdepaChileExports(SignalSource):
    """Monthly Chile->UK fresh blueberry export tonnage (origin customs)."""

    series = "odepa_chile_uk_exports"
    freq = "M"
    unit = "tonnes"

    def __init__(self, year_start: int = 2018, year_end: int | None = None):
        self.year_start = year_start
        self.year_end = year_end or _dt.date.today().year

    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        resources = _resource_ids()
        agg: dict[tuple[int, int], float] = {}
        for year in range(self.year_start, self.year_end + 1):
            rid = resources.get(year)
            if not rid:
                continue
            for month, kg in _fetch_year(rid):
                agg[(year, month)] = agg.get((year, month), 0.0) + kg

        records = [
            {
                "series": self.series,
                "ref_period": _dt.date(y, m, 1).isoformat(),
                "freq": self.freq,
                "key": "Chile",
                "value": kg / KG_PER_TONNE,
                "unit": self.unit,
            }
            for (y, m), kg in agg.items()
        ]
        return self._tidy(records, vintage_date)


if __name__ == "__main__":
    df = OdepaChileExports(year_start=2023).fetch()
    print(f"rows: {len(df)}  range: {df['ref_period'].min()}..{df['ref_period'].max()}")
    print(df.sort_values("ref_period").tail(8).to_string(index=False))
