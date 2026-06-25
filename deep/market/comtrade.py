"""Chilean blueberry export destinations from UN Comtrade -- the price each market pays.

Comtrade publishes, for reporter=Chile, flow=export, commodity=HS 081040 (fresh
cranberries/blueberries of genus Vaccinium), the annual value (USD) and net weight
(kg) to every partner country. value/weight = the realised CIF unit value -- what
Chilean fruit actually fetched in that market. The free "preview" endpoint needs no
key (verified reachable 2026-06; up to 500 rows/call), so the weekly cron refreshes
a committed CSV and the rest of the stack reads that offline.

HS 081040 is the genus-Vaccinium line (cultivated blueberry dominates Chilean
exports); the same code HMRC splits to CN8 08104050 on the UK side.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

from deep.config import DATA_DIR, HS6

CACHE = DATA_DIR / "market" / "chile_destinations.csv"
PERU_CACHE = DATA_DIR / "market" / "peru_destinations.csv"
_CHILE = 152
PERU = 604
_HS = HS6
_PREVIEW = ("https://comtradeapi.un.org/public/v1/preview/C/A/HS"
            "?reporterCode={rep}&period={yr}&cmdCode={hs}&flowCode=X"
            "&partnerCode=&motCode=0&customsCode=C00")

# Partner M49 -> display name. Only the partners that matter for Chilean blueberry;
# anything unmapped is carried through under its numeric code so nothing is dropped.
PARTNER = {
    842: "United States", 528: "Netherlands", 156: "China", 410: "South Korea",
    826: "United Kingdom", 276: "Germany", 124: "Canada", 56: "Belgium",
    490: "Other Asia, nes", 724: "Spain", 392: "Japan", 32: "Argentina",
    158: "Taiwan", 344: "Hong Kong", 484: "Mexico", 380: "Italy", 36: "Australia",
    702: "Singapore", 608: "Philippines", 458: "Malaysia", 250: "France",
    752: "Sweden", 372: "Ireland", 76: "Brazil", 170: "Colombia", 218: "Ecuador",
    784: "United Arab Emirates", 634: "Qatar", 682: "Saudi Arabia",
    376: "Israel", 616: "Poland",
    # added for Peru's destination set
    699: "India", 764: "Thailand", 643: "Russia", 188: "Costa Rica", 152: "Chile",
}


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _fetch_year(year: int, reporter: int = _CHILE, retries: int = 4, hs: str = _HS) -> pd.DataFrame:
    url = _PREVIEW.format(rep=reporter, yr=year, hs=hs)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                payload = json.load(r)
            rows = payload.get("data", []) or []
            out = []
            for row in rows:
                code = int(_num(row, "partnerCode"))
                if code == 0:                      # 0 == "World" aggregate, skip
                    continue
                val, wgt = _num(row, "primaryValue"), _num(row, "netWgt")
                if val <= 0 or wgt <= 0:
                    continue
                out.append({
                    "year": year,
                    "partner_code": code,
                    "destination": PARTNER.get(code, f"M49-{code}"),
                    "value_usd": val,
                    "net_kg": wgt,
                    "cif_usd_kg": val / wgt,
                })
            # the preview endpoint can emit duplicate records per partner
            return pd.DataFrame(out).drop_duplicates(subset=["year", "partner_code"])
        except Exception as e:                     # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade fetch failed for {year}: {last}")


def refresh(years: list[int], reporter: int = _CHILE, cache=CACHE) -> pd.DataFrame:
    """Fetch the given years for `reporter` and (re)write its cache, merging by year."""
    fresh = pd.concat([_fetch_year(y, reporter) for y in years], ignore_index=True)
    if cache.exists():
        old = pd.read_csv(cache)
        old = old[~old["year"].isin(years)]        # replace refreshed years wholesale
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "value_usd"], ascending=[True, False])
    cache.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(cache, index=False)
    return fresh


def load(cache=CACHE) -> pd.DataFrame:
    """Read a cached destinations table (offline). Empty frame if never fetched."""
    if not cache.exists():
        return pd.DataFrame(columns=["year", "partner_code", "destination",
                                     "value_usd", "net_kg", "cif_usd_kg"])
    return pd.read_csv(cache)


def latest_year(df: pd.DataFrame | None = None) -> int:
    df = load() if df is None else df
    return int(df["year"].max()) if len(df) else 0


if __name__ == "__main__":                         # python -m nowcast.market.comtrade
    import datetime as _dt
    this = _dt.date.today().year
    yrs = [this - 3, this - 2, this - 1]
    for rep, cache, who in ((_CHILE, CACHE, "Chile"), (PERU, PERU_CACHE, "Peru")):
        df = refresh(yrs, reporter=rep, cache=cache)
        print(f"{who}: cached {len(df)} rows -> {cache}")
