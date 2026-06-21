"""China blueberry snapshot -- the gated bloc, and the world's biggest hole in FAOSTAT.

China's GACC customs is JS-challenge anti-bot gated (no free feed), and FAOSTAT carries NO
China blueberry PRODUCTION at all -- so the world's #1 producer is invisible in the base
layers. This hand-curated snapshot (`data/atlas/china.csv`, press/GACC/China-Daily) fills
both: China's domestic PRODUCTION (the dominant fact), its IMPORTS by origin, and the
PRICE collapse.

The big picture it captures: China grew ~810 kt domestically in 2025 (2x in five years,
world #1 by far) while importing only ~39 kt -- it grows ~20x what it buys. Domestic
oversupply has crashed premium prices ~50%, which complicates Peru's Chancay-driven pivot
into China as a "premium" market. Snapshot, hand-refreshed -- same contract as the committees.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "china.csv"


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=["year", "kind", "detail", "value", "unit", "note", "source"])
    return pd.read_csv(CACHE)


def latest(kind: str, detail: str) -> float | None:
    df = load()
    sub = df[(df["kind"] == kind) & (df["detail"] == detail)].sort_values("year")
    return float(sub.iloc[-1]["value"]) if len(sub) else None


def headline() -> str | None:
    """One-line China summary -- leads with PRODUCTION (the dominant, missing-from-FAOSTAT fact)."""
    bits = []
    prod = latest("production", "China total")
    if prod:
        bits.append(f"world #1 producer {prod/1e6:.2f} Mt (2025)")
    imp = latest("import", "Total")
    if imp:
        bits.append(f"imports {imp/1000:.0f}kt (Peru 89%)")
    if latest("price", "premium farm-gate"):
        bits.append("prices -50% (oversupply)")
    return " · ".join(bits) if bits else None


if __name__ == "__main__":
    print(headline())
    print(load().to_string(index=False))
