"""The global bilateral flow + price grid for blueberries (HS 081040).

The Comtrade sweep (`comtrade_sweep`) ranks each country's *total* trade; this
fills the cells *between* them -- for every major exporter, its exports to every
partner, with the realised unit value (value/weight = the price that lane fetched).
It generalises the per-origin destination tables that existed only for Chile and
Peru (`market/comtrade.py`) to the whole exporter target set, so the registry's
"bilateral flow + price matrix" row is real globally, not just two lanes.

One preview call per exporter (reporterCode=code, all partners, partner2Code=0 --
the same aggregate-row pin the sweep uses), committed to
`data/atlas/comtrade_bilateral.csv`. No key. Annual; the latest ~2 years are
provisional (staggered reporting -- see `comtrade_sweep`).
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR, countries, comtrade_sweep, hs_codes

CACHE = ATLAS_DIR / "comtrade_bilateral.csv"
_URL = ("https://comtradeapi.un.org/public/v1/preview/C/A/HS"
        "?reporterCode={rep}&period={yr}&cmdCode={hs}&flowCode=X"
        "&partnerCode=&partner2Code=0&motCode=0&customsCode=C00")
_COLS = ["year", "exporter_code", "exporter", "importer_code", "importer",
         "value_usd", "net_kg", "unit_usd_kg", "provisional"]
_MIN_KG = 1_000          # drop trace lanes (tiny-N unit values lie -- HANDOFF gotcha)


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _fetch(reporter: int, year: int, hs: str, retries: int = 4) -> list[dict]:
    url = _URL.format(rep=reporter, yr=year, hs=hs)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("data", []) or []
        except Exception as e:                         # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade matrix fetch failed (reporter={reporter} {year}): {last}")


def _exporter_codes(year: int | None) -> list[int]:
    """The exporter target set (95% of trade) from the sweep, if available."""
    ts = comtrade_sweep.target_set("exporter", year=year, include_provisional=year is not None)
    if not ts.empty:
        return [int(c) for c in ts["reporter_code"]]
    return [604, 528, 724, 152, 504, 842, 484, 124, 616, 710]   # fallback top exporters


def refresh(years: list[int], exporters: list[int] | None = None,
            names: dict[int, str] | None = None) -> pd.DataFrame:
    """Fetch the bilateral export grid for the exporter target set; (re)write cache."""
    hs = hs_codes.hs6("blueberry")
    names = names or countries.name_map()
    parts = []
    for year in years:
        codes = exporters if exporters is not None else _exporter_codes(None)
        prov = comtrade_sweep.is_provisional(year)
        for rep in codes:
            rows = []
            for r in _fetch(rep, year, hs):
                pc = int(_num(r, "partnerCode"))
                if pc == 0:                            # World aggregate, skip
                    continue
                val, wgt = _num(r, "primaryValue"), _num(r, "netWgt")
                if val <= 0 or wgt < _MIN_KG:
                    continue
                rows.append({"year": year, "exporter_code": rep,
                             "exporter": names.get(rep, f"M49-{rep}"),
                             "importer_code": pc, "importer": names.get(pc, f"M49-{pc}"),
                             "value_usd": val, "net_kg": wgt,
                             "unit_usd_kg": round(val / wgt, 4), "provisional": prov})
            parts.append(pd.DataFrame(rows, columns=_COLS)
                         .drop_duplicates(subset=["year", "exporter_code", "importer_code"]))
            time.sleep(0.4)
    fresh = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=_COLS)
    if CACHE.exists() and not fresh.empty:
        old = pd.read_csv(CACHE)
        old = old[~old["year"].isin(years)]
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "value_usd"], ascending=[True, False]).reset_index(drop=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def lanes(exporter: str | None = None, importer: str | None = None,
          year: int | None = None) -> pd.DataFrame:
    """Filter the grid to an exporter and/or importer (latest year if None)."""
    df = load()
    if df.empty:
        return df
    year = year or int(df["year"].max())
    df = df[df["year"] == year]
    if exporter is not None:
        df = df[df["exporter"] == exporter]
    if importer is not None:
        df = df[df["importer"] == importer]
    return df.sort_values("value_usd", ascending=False).reset_index(drop=True)


if __name__ == "__main__":                             # python -m atlas.comtrade_matrix
    this = _dt.date.today().year
    df = refresh([this - 4, this - 3])                 # latest non-provisional window
    print(f"cached {len(df)} bilateral lanes -> {CACHE}")
    if len(df):
        yr = int(df[~df["provisional"]]["year"].max()) if (~df["provisional"]).any() \
            else int(df["year"].max())
        top = lanes(year=yr).head(10)
        print(f"\ntop blueberry lanes {yr} (USD/kg):")
        print(top[["exporter", "importer", "value_usd", "net_kg", "unit_usd_kg"]]
              .to_string(index=False))
