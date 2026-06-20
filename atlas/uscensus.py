"""US blueberry imports by origin -- the live US slice (US Census trade API).

The US is the world's #1 blueberry importer, so it's the biggest piece of the global
reconciliation residual. The US Census intltrade/imports/hs endpoint gives US customs
imports by HS x country x month (~6-week lag) -- the US analog of Eurostat for the EU.

It needs a FREE API key (instant email signup at api.census.gov/data/key_signup.html).
Set CENSUS_API_KEY and this becomes the live, current US importer layer; without it this
is a no-op and global_reconcile.py falls back to the Comtrade US slice (solid, but lags to
2024). Same "one key away" contract as the USDA-AMS MARS API. Fresh blueberries = the
HTS-10 codes under HS 0810.40 (cultivated + wild).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import time
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "us_imports.csv"
_API = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
_CODES = ["0810400024", "0810400026"]                 # fresh blueberries: cultivated + wild
_COLS = ["year", "month", "partner_code", "partner", "value_usd", "net_kg"]


def _key() -> str | None:
    return os.environ.get("CENSUS_API_KEY")


def _fetch(code: str, start: str, end: str, key: str, retries: int = 4) -> list | None:
    url = (f"{_API}?get=CTY_CODE,CTY_NAME,GEN_VAL_MO,GEN_QY1_MO&I_COMMODITY={code}"
           f"&time=from+{start}+to+{end}&key={key}")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:                             # noqa: BLE001
            last = e; time.sleep(2 ** attempt)
    raise RuntimeError(f"Census fetch failed ({code}): {last}")


def _is_country(code: str, name: str) -> bool:
    # drop Census aggregates (TOTAL FOR ALL COUNTRIES, regions like '0024'); keep real partners
    return bool(name) and "TOTAL" not in name.upper() and not name.startswith("(")


def refresh(start: str = "2022-01", end: str | None = None) -> pd.DataFrame:
    """Live US imports by origin (needs CENSUS_API_KEY); else a no-op returning empty."""
    key = _key()
    if not key:
        print("CENSUS_API_KEY not set -> skipping live US slice (Comtrade fallback in use)")
        return pd.DataFrame(columns=_COLS)
    end = end or _dt.date.today().strftime("%Y-%m")
    cells: dict[tuple, dict] = {}
    for code in _CODES:
        rows = _fetch(code, start, end, key)
        if not rows:
            continue
        head = rows[0]
        ix = {h: i for i, h in enumerate(head)}
        for r in rows[1:]:
            cc, name, val, qty, t = (r[ix["CTY_CODE"]], r[ix["CTY_NAME"]], r[ix["GEN_VAL_MO"]],
                                     r[ix["GEN_QY1_MO"]], r[ix["time"]])
            if not _is_country(cc, name):
                continue
            y, m = t.split("-")
            k = (int(y), int(m), cc, name.title())
            c = cells.setdefault(k, {"value_usd": 0.0, "net_kg": 0.0})
            c["value_usd"] += float(val or 0)
            c["net_kg"] += float(qty or 0)                 # GEN_QY1_MO is kg for 0810.40
    out = [{"year": y, "month": m, "partner_code": cc, "partner": nm,
            "value_usd": round(v["value_usd"]), "net_kg": round(v["net_kg"])}
           for (y, m, cc, nm), v in cells.items() if v["value_usd"] > 0]
    df = pd.DataFrame(out, columns=_COLS).sort_values(["year", "month", "net_kg"],
                                                      ascending=[True, True, False])
    if not df.empty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE, index=False)
    return df


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


if __name__ == "__main__":
    df = refresh()
    print(f"{len(df)} US import rows" + ("" if len(df) else " (set CENSUS_API_KEY to populate)"))
