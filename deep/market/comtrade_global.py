"""UN Comtrade -- the global blueberry trade map (HS 081040).

One free source gives the whole world: for each major country we pull its total
imports (flow=M) and exports (flow=X) of fresh blueberries vs World, annual.
Ranked, this is the global league table -- who feeds the planet, who buys it, and
where the UK sits. The lane-level destination detail lives in `comtrade.py`; this
module is the breadth layer (HANDOFF Phase 1).

Cache: data/market/global_trade.csv  (year, role, country_code, country,
value_usd, net_kg, usd_per_kg). Reads are look-ahead-free at the annual grain.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from ..config import DATA_DIR

CACHE = DATA_DIR / "market" / "global_trade.csv"
_HS = "081040"
# partner2Code=0 is essential: it pins the World-World aggregate (the true
# reporter total). Without it the preview also returns a full partner2 breakdown
# that, summed, double-counts the total for countries that report it (UK, DE…).
_PREVIEW = ("https://comtradeapi.un.org/public/v1/preview/C/A/HS"
            "?reporterCode={rep}&period={yr}&cmdCode={hs}&flowCode={flow}"
            "&partnerCode=0&partner2Code=0&motCode=0&customsCode=C00")
_HEADERS = {"User-Agent": "uk-blueberry-atlas/0.1 (research)"}

# M49 code -> display name. The countries that carry world blueberry trade
# (big exporters and/or importers). Many appear on both sides (NL, ES, US, CA).
COUNTRIES = {
    604: "Peru", 152: "Chile", 724: "Spain", 484: "Mexico", 504: "Morocco",
    528: "Netherlands", 710: "South Africa", 616: "Poland", 124: "Canada",
    842: "United States", 32: "Argentina", 156: "China", 620: "Portugal",
    276: "Germany", 826: "United Kingdom", 251: "France", 380: "Italy",
    56: "Belgium", 643: "Russia", 392: "Japan", 752: "Sweden", 372: "Ireland",
}


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _fetch_flow(year: int, flow: str, retries: int = 4) -> dict[int, tuple[float, float]]:
    """One batched call: every COUNTRIES reporter vs World for a flow.

    With partnerCode=0 AND partner2Code=0 the endpoint returns exactly one
    World-World aggregate row per reporter — the authoritative total. (A dict
    keyed by reporter dedups any duplicate preview emissions.) Returns
    {reporter_code: (value_usd, net_kg)}.
    """
    reps = ",".join(str(c) for c in COUNTRIES)
    url = _PREVIEW.format(rep=reps, yr=year, hs=_HS, flow=flow)
    delay = 2.0
    rows: list[dict] = []
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=90)
            if resp.status_code == 200:
                rows = resp.json().get("data", []) or []
                break
            if attempt == retries:
                resp.raise_for_status()
        except requests.RequestException:
            if attempt == retries:
                raise
        time.sleep(delay)
        delay *= 2
    out: dict[int, tuple[float, float]] = {}
    for r in rows:
        rc = int(_num(r, "reporterCode"))
        out[rc] = (_num(r, "primaryValue"), _num(r, "netWgt"))  # one row per reporter
    return out


# Bellwether importers that must ALL be present for a year to count as "complete".
# China is the slowest major reporter, so requiring it screens out partial years.
_BELLWETHERS = (842, 276, 826, 124, 156)  # US, Germany, UK, Canada, China


def latest_complete_year() -> int:
    """Most recent year with full coverage: every bellwether importer present
    and >$30m. Annual data lags, so walk back from last year until solid."""
    import datetime
    y0 = datetime.date.today().year
    for y in range(y0 - 1, y0 - 6, -1):
        try:
            imp = _fetch_flow(y, "M")
        except Exception:
            imp = {}
        if all(imp.get(c, (0.0, 0.0))[0] > 3e7 for c in _BELLWETHERS):
            return y
        time.sleep(1.0)
    return y0 - 3


def refresh(year: int | None = None, cache=CACHE) -> pd.DataFrame:
    """Pull imports + exports vs World for every country (2 calls), rank, cache.
    year=None -> auto-detect the latest complete year."""
    if year is None:
        year = latest_complete_year()
    recs = []
    for flow, role in (("M", "importer"), ("X", "exporter")):
        for code, (val, kg) in _fetch_flow(year, flow).items():
            if (val <= 0 and kg <= 0) or code not in COUNTRIES:
                continue
            recs.append({"year": year, "role": role, "country_code": code,
                         "country": COUNTRIES[code], "value_usd": val, "net_kg": kg,
                         "usd_per_kg": (val / kg) if kg else float("nan")})
        time.sleep(1.0)
    df = pd.DataFrame(recs)
    if not df.empty:
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.sort_values(["role", "value_usd"], ascending=[True, False]).to_csv(cache, index=False)
    return df


def load(cache=CACHE) -> pd.DataFrame:
    if not cache.exists():
        return pd.DataFrame(columns=["year", "role", "country_code", "country",
                                     "value_usd", "net_kg", "usd_per_kg"])
    return pd.read_csv(cache)


def _table(role: str, n: int, df: pd.DataFrame | None = None) -> pd.DataFrame:
    df = load() if df is None else df
    if df.empty:
        return df
    return (df[df["role"] == role].sort_values("value_usd", ascending=False)
            .head(n).reset_index(drop=True))


def top_importers(n: int = 8, df=None) -> pd.DataFrame:
    return _table("importer", n, df)


def top_exporters(n: int = 8, df=None) -> pd.DataFrame:
    return _table("exporter", n, df)


def uk_import_rank(df: pd.DataFrame | None = None) -> tuple[int, int]:
    """(rank, total) of the UK among world importers, by value. (0, 0) if absent."""
    imp = _table("importer", 999, df)
    if imp.empty:
        return 0, 0
    order = imp["country"].tolist()
    return (order.index("United Kingdom") + 1 if "United Kingdom" in order else 0), len(order)


if __name__ == "__main__":
    import sys
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else None
    out = refresh(yr)
    print(f"wrote {len(out)} rows -> {CACHE}")
    if not out.empty:
        print("\nTop importers:")
        print(top_importers(6, out)[["country", "value_usd", "net_kg"]].to_string(index=False))
        print("\nTop exporters:")
        print(top_exporters(6, out)[["country", "value_usd", "net_kg"]].to_string(index=False))
