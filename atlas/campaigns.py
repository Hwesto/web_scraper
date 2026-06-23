"""Current-season CAMPAIGN tracker -- the real-time layer Comtrade/FAOSTAT can't reach.

Grower committees and a few official agencies report the season as it happens, ~18 months
ahead of UN Comtrade. This consolidates the confirmed current-season totals for every major
exporter (Peru ProArandanos, Chile Comite de Arandanos, South Africa Berries ZA, Argentina
ABC, Mexico Aneberries, Spain FEPEX/Freshuelva, Morocco APEFEL) -- see FRONTIER_SOURCES.md
for the full availability map and per-country format/verdict.

Honesty about cadence: only the USA has a true free current-season API (USDA AMS); every
source here is a committee PDF or press relay, so this is a hand-curated SEASON snapshot
(`data/atlas/campaigns.csv`), refreshed a few times per campaign -- same contract as the
USDA-GAIN filenames. Figures are press/committee-reported and subject to revision.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "campaigns.csv"
# headline metric preference (first present wins) + how to label it honestly
_PRIMARY = [
    ("export_total", "season"), ("export_total_fresh", "season (fresh)"),
    ("export_ytd", "to date"), ("production_total", "production"),
    ("huelva_production", "Huelva prod"),
]


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=["country", "season", "metric", "value", "unit", "as_of", "source"])
    return pd.read_csv(CACHE)


def latest(country: str) -> pd.DataFrame:
    """All metrics for a country's most recent cached season."""
    df = load()
    sub = df[df["country"] == country]
    if sub.empty:
        return sub
    season = sorted(sub["season"].unique())[-1]
    return sub[sub["season"] == season]


def headline(country: str) -> str | None:
    """One-line current-season summary for the card, or None if uncached."""
    s = latest(country)
    if s.empty:
        return None
    for metric, label in _PRIMARY:
        row = s[s["metric"] == metric]
        if len(row):
            break
    else:
        return None
    val = float(row.iloc[0]["value"])
    yoy = s[s["metric"] == "yoy_growth"]
    yoy_s = f" ▲{float(yoy.iloc[0]['value']):.0f}%" if len(yoy) and float(yoy.iloc[0]['value']) >= 0 else \
            (f" ▼{abs(float(yoy.iloc[0]['value'])):.0f}%" if len(yoy) else "")
    season = row.iloc[0]["season"]
    return f"{season} {label}: {val/1000:.0f}kt{yoy_s}"


def countries() -> list[str]:
    return sorted(load()["country"].unique())


if __name__ == "__main__":
    for c in countries():
        print(f"{c:14s} {headline(c)}")
