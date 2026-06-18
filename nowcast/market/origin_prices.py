"""Origin-side export price for EVERY major UK-supply country, via UN Comtrade.

We already have the UK-landed CIF for every origin (HMRC, price.import_unit_value).
This adds the symmetric origin-side view we only had for Chile: each supplier
country's own export unit value (value/weight = FOB-ish USD/kg) for blueberries
(HS 081040), pulled with ONE uniform method for all reporters -- so Peru, Morocco,
Spain, South Africa, Argentina, Portugal, Poland and the Netherlands get the same
treatment Chile's DUS feed gives, just annual and less granular.

For each origin we capture two partners: World (the country's overall export
price) and the UK (826) specifically (the price of fruit actually shipped to our
market). Pairing fob_usd_kg(->UK) against the HMRC UK CIF for the same origin
brackets the freight+insurance+margin wedge per country.

Same free preview endpoint as comtrade.py (no key, verified 2026-06). Cron writes
the committed CSV; the stack reads it offline. Annual only -- the weekly/named
richness is Chile-specific (its DUS feed) and not replicable per country here.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.request

import pandas as pd

from nowcast.config import DATA_DIR
from nowcast.market.comtrade import _HS, _PREVIEW

CACHE = DATA_DIR / "market" / "origin_export_prices.csv"
# major UK blueberry origins: reporter M49 -> name (covers ~all material supply)
ORIGINS = {152: "Chile", 604: "Peru", 504: "Morocco", 724: "Spain",
           710: "South Africa", 32: "Argentina", 620: "Portugal",
           616: "Poland", 528: "Netherlands"}
_DESTS = {0: "World", 826: "United Kingdom"}
_COLS = ["origin", "reporter_code", "year", "dest", "value_usd", "net_kg", "fob_usd_kg"]


def _fetch(reporter: int, year: int, retries: int = 4) -> list[dict]:
    """All partner rows for one reporter-year (export, HS081040)."""
    url = _PREVIEW.format(rep=reporter, yr=year, hs=_HS)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r).get("data", []) or []
        except Exception as e:                     # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade fetch failed for reporter={reporter} {year}: {last}")


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def refresh(years: list[int]) -> pd.DataFrame:
    """Fetch World + UK export unit values for every origin, (re)write the cache."""
    rows = []
    for code, name in ORIGINS.items():
        for year in years:
            by_partner = {int(_num(r, "partnerCode")): r for r in _fetch(code, year)}
            for dcode, dname in _DESTS.items():
                r = by_partner.get(dcode)
                if not r:
                    continue
                val, wgt = _num(r, "primaryValue"), _num(r, "netWgt")
                if val <= 0 or wgt <= 0:
                    continue
                rows.append({"origin": name, "reporter_code": code, "year": year,
                             "dest": dname, "value_usd": val, "net_kg": wgt,
                             "fob_usd_kg": round(val / wgt, 4)})
            time.sleep(0.5)                        # polite between reporter-years
    fresh = pd.DataFrame(rows, columns=_COLS)
    if CACHE.exists() and not fresh.empty:
        old = pd.read_csv(CACHE)
        old = old[~old["year"].isin(years)]
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "dest", "fob_usd_kg"], ascending=[True, True, False])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def by_country(year: int | None = None, dest: str = "United Kingdom") -> pd.DataFrame:
    """Per-origin export FOB (USD/kg) for one year/destination, richest first."""
    df = load()
    if df.empty:
        return df
    year = year or int(df["year"].max())
    sub = df[(df["year"] == year) & (df["dest"] == dest)]
    return sub.sort_values("net_kg", ascending=False).reset_index(drop=True)


if __name__ == "__main__":                         # python -m nowcast.market.origin_prices
    this = _dt.date.today().year
    df = refresh([this - 2, this - 1])
    print(f"cached {len(df)} rows -> {CACHE}")
    uk = by_country(dest="United Kingdom")
    print(f"\nexport FOB to UK, {uk['year'].iloc[0] if len(uk) else '-'} (USD/kg):")
    print(uk[["origin", "fob_usd_kg", "net_kg"]].to_string(index=False))
