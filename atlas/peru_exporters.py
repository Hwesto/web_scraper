"""Peru named-exporter ranking -- a *depth-frontier* dataset, not a base layer.

This is the cutting edge the global base layers (Comtrade, FAOSTAT) cannot see: who
actually shipped Peru's blueberries, by company, with volume + FOB value + YoY growth.
It's the granularity paid services (Agronometrics, iQonsulting) charge for -- and it's
free, from ProArandanos season reports / Agrodata / SUNAT customs, surfaced each year in
the Peruvian business press.

Honesty about cadence: this is a hand-verified **annual season snapshot**
(`data/atlas/peru_exporters.csv`), refreshed once per campaign -- same contract as the
USDA-GAIN filenames, NOT a live feed. The genuinely-live version (SUNAT Aduanet weekly
by-shipment) is gated and is the next rung of the frontier. Committed so the figure has
provenance and the atlas can show named-exporter depth for Peru.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "peru_exporters.csv"


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=["season", "rank", "company", "volume_t",
                                     "fob_usd_m", "yoy_pct", "source"])
    return pd.read_csv(CACHE).sort_values("rank").reset_index(drop=True)


def top(n: int = 10) -> pd.DataFrame:
    return load().head(n)


if __name__ == "__main__":
    df = load()
    print(f"{len(df)} named Peru exporters, season {df['season'].iloc[0] if len(df) else '-'}")
    print(df[["rank", "company", "volume_t", "fob_usd_m", "yoy_pct"]].to_string(index=False))
