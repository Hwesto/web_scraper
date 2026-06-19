"""Monthly bilateral flow + price for blueberries (HS 081040) -- the seasonality layer.

The annual grid (`comtrade_matrix`) says how much each lane moved in a year; this
says *when*. Blueberry trade is intensely seasonal -- the hemispheres relay supply
through the calendar (Peru/Chile/South Africa fill the Northern winter, Spain/
Morocco the shoulders) -- so monthly resolution is where the counter-season story
lives. Same free Comtrade preview, monthly table (/C/M/), period=YYYYMM.

One call per exporter-half-year (months split 1-6 / 7-12 to stay under the 500-row
preview cap), partner2Code=0 aggregate pin, committed to
`data/atlas/comtrade_monthly.csv`. Monthly data lags more than annual, so recent
months are sparse; `seasonality()` averages each calendar month across years to
expose the profile robustly.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR, countries, comtrade_matrix, comtrade_sweep, hs_codes

CACHE = ATLAS_DIR / "comtrade_monthly.csv"
_URL = ("https://comtradeapi.un.org/public/v1/preview/C/M/HS"
        "?reporterCode={rep}&period={periods}&cmdCode={hs}&flowCode=X"
        "&partnerCode=&partner2Code=0&motCode=0&customsCode=C00")
_COLS = ["year", "month", "exporter_code", "exporter", "importer_code", "importer",
         "value_usd", "net_kg", "unit_usd_kg"]
_MIN_KG = 1_000          # trace lanes lie (HANDOFF gotcha)
_HALVES = ([1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12])


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _period(row: dict, year: int) -> tuple[int, int]:
    """(year, month) for a monthly row. Comtrade gives integer refYear/refMonth and
    a `period` that is often a STRING ('202401') -- prefer the former, parse the
    latter as text (not via _num, which only reads numbers)."""
    ry, rm = row.get("refYear"), row.get("refMonth")
    if ry and rm:
        return int(ry), int(rm)
    p = row.get("period")
    if p:
        p = int(str(p))
        return p // 100, p % 100
    return year, 0


def _fetch(reporter: int, periods: list[int], hs: str, retries: int = 4) -> list[dict]:
    url = _URL.format(rep=reporter, periods=",".join(map(str, periods)), hs=hs)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("data", []) or []
        except Exception as e:                         # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade monthly fetch failed (reporter={reporter} {periods[0]}..): {last}")


def refresh(years: list[int], exporters: list[int] | None = None,
            names: dict[int, str] | None = None) -> pd.DataFrame:
    """Fetch monthly export lanes for the exporter target set; (re)write the cache."""
    hs = hs_codes.hs6("blueberry")
    names = names or countries.name_map()
    codes = exporters if exporters is not None else comtrade_matrix._exporter_codes(None)
    rows = []
    for year in years:
        for rep in codes:
            for half in _HALVES:
                periods = [year * 100 + m for m in half]
                for r in _fetch(rep, periods, hs):
                    pc = int(_num(r, "partnerCode"))
                    if pc == 0:
                        continue
                    val, wgt = _num(r, "primaryValue"), _num(r, "netWgt")
                    if val <= 0 or wgt < _MIN_KG:
                        continue
                    yr, mo = _period(r, year)
                    if not 1 <= mo <= 12:             # skip any non-monthly/aggregate row
                        continue
                    rows.append({"year": yr, "month": mo,
                                 "exporter_code": rep, "exporter": names.get(rep, f"M49-{rep}"),
                                 "importer_code": pc, "importer": names.get(pc, f"M49-{pc}"),
                                 "value_usd": val, "net_kg": wgt,
                                 "unit_usd_kg": round(val / wgt, 4)})
                time.sleep(0.4)
    fresh = pd.DataFrame(rows, columns=_COLS).drop_duplicates(
        subset=["year", "month", "exporter_code", "importer_code"])
    if CACHE.exists() and not fresh.empty:
        old = pd.read_csv(CACHE)
        old = old[~old["year"].isin(years)]
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "month", "value_usd"],
                              ascending=[True, True, False]).reset_index(drop=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def seasonality(exporter: str, importer: str | None = None) -> pd.DataFrame:
    """Each calendar month's share of an exporter's annual volume, averaged across
    the cached years -- the lane's seasonal signature (robust to sparse recent months)."""
    df = load()
    if df.empty:
        return df
    df = df[df["exporter"] == exporter]
    if importer is not None:
        df = df[df["importer"] == importer]
    if df.empty:
        return df
    by_ym = df.groupby(["year", "month"])["net_kg"].sum().reset_index()
    by_ym["year_total"] = by_ym.groupby("year")["net_kg"].transform("sum")
    by_ym["share"] = by_ym["net_kg"] / by_ym["year_total"]
    prof = by_ym.groupby("month")["share"].mean().reset_index()
    prof["share"] = prof["share"].round(4)
    return prof.sort_values("month").reset_index(drop=True)


if __name__ == "__main__":                             # python -m atlas.comtrade_monthly
    this = _dt.date.today().year
    df = refresh([this - 3, this - 2])                 # reasonably-complete monthly years
    print(f"cached {len(df)} monthly lanes -> {CACHE}")
    for who in ("Peru", "Chile", "Spain"):
        prof = seasonality(who)
        if len(prof):
            peak = prof.loc[prof["share"].idxmax()]
            print(f"  {who}: peak month {int(peak['month'])} ({peak['share']*100:.0f}% of annual volume)")
