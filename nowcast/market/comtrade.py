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

from nowcast.config import DATA_DIR

CACHE = DATA_DIR / "market" / "chile_destinations.csv"
_CHILE = 152
_HS = "081040"
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
}


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _fetch_year(year: int, retries: int = 4) -> pd.DataFrame:
    url = _PREVIEW.format(rep=_CHILE, yr=year, hs=_HS)
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
            return pd.DataFrame(out)
        except Exception as e:                     # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade fetch failed for {year}: {last}")


def refresh(years: list[int]) -> pd.DataFrame:
    """Fetch the given years and (re)write the committed cache, merging by year."""
    fresh = pd.concat([_fetch_year(y) for y in years], ignore_index=True)
    if CACHE.exists():
        old = pd.read_csv(CACHE)
        old = old[~old["year"].isin(years)]        # replace refreshed years wholesale
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "value_usd"], ascending=[True, False])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    """Read the cached destinations table (offline). Empty frame if never fetched."""
    if not CACHE.exists():
        return pd.DataFrame(columns=["year", "partner_code", "destination",
                                     "value_usd", "net_kg", "cif_usd_kg"])
    return pd.read_csv(CACHE)


def latest_year(df: pd.DataFrame | None = None) -> int:
    df = load() if df is None else df
    return int(df["year"].max()) if len(df) else 0


if __name__ == "__main__":                         # python -m nowcast.market.comtrade
    import datetime as _dt
    this = _dt.date.today().year
    df = refresh([this - 3, this - 2, this - 1])
    print(f"cached {len(df)} rows -> {CACHE}")
    last = df[df["year"] == latest_year(df)].head(8)
    print(last[["destination", "cif_usd_kg", "net_kg"]].to_string(index=False))
