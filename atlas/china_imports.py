"""China blueberry imports by origin -- a press/GACC SNAPSHOT (the one gated bloc).

China's GACC customs portal is behind a JS-challenge anti-bot (stats.customs.gov.cn 412s
automated requests; translating doesn't help -- see registry/FRONTIER_SOURCES.md), and the
HS-level by-origin data only surfaces via resellers/press (Tridge, Agronometrics, Produce
Report, Blueberries Consulting). So -- like the Peru/Mexico committee data -- this is a
hand-curated annual SNAPSHOT (`data/atlas/china_imports.csv`), not a live feed.

It captures what Comtrade can't yet show: the CURRENT surge. China 2024 ~38.7kt (Peru 89%);
2025 Peru->China value +153% ($105M->$266M) on the new Chancay direct shipping route.
Comtrade still backstops China lagged (mainland 39kt + Hong Kong 30kt 2024) for the backtest.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "china_imports.csv"


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=["year", "origin", "imports_t", "share_pct", "value_musd",
                                     "note", "source"])
    return pd.read_csv(CACHE)


def headline() -> str | None:
    """One-line current-China-demand summary for the China card."""
    df = load()
    if df.empty:
        return None
    y24 = df[(df["year"] == 2024) & (df["origin"] == "Total")]
    bits = []
    if len(y24):
        peru = df[(df["year"] == 2024) & (df["origin"] == "Peru")]
        sh = f" (Peru {int(peru.iloc[0]['share_pct'])}%)" if len(peru) else ""
        bits.append(f"2024 imports {float(y24.iloc[0]['imports_t'])/1000:.0f}kt{sh}")
    surge = df[(df["year"] == 2025) & (df["origin"] == "Peru")]
    if len(surge):
        bits.append("2025 Peru +153% (Chancay)")
    return " · ".join(bits) if bits else None


if __name__ == "__main__":
    print(headline())
    print(load().to_string(index=False))
