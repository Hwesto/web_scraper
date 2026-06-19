"""Peru blueberry CAMPAIGN tracker -- the real-time layer Comtrade cannot reach.

ProArandanos (the Peruvian blueberry growers/exporters' association) reports the season
as it happens: cumulative export tonnage, the peak week, regional split. This is genuinely
*current* -- the 2025/26 campaign closed at a record ~383 kt while Comtrade's latest final
Peru figure is still 2024 (326 kt). The forward edge.

Honesty about the source: ProArandanos' own site is a Power-BI dashboard / often refuses
direct fetches, and the weekly numbers surface through the Peruvian agri-press
(FreshPlaza, Portalfruticola, Gestion) as campaign snapshots -- NOT a machine-readable
weekly feed. So this is a hand-curated **season snapshot** (`data/atlas/peru_campaign.csv`),
refreshed a few times per campaign, same contract as the USDA-GAIN filenames and the
named-exporter table. A true weekly time series would need scraping the dashboard's
backing API (the next rung). Figures are press-reported and subject to revision.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "peru_campaign.csv"


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=["season", "metric", "value", "unit", "as_of", "source"])
    return pd.read_csv(CACHE)


def latest() -> dict:
    """The latest season's metrics as a {metric: value} dict (empty if none cached)."""
    df = load()
    if df.empty:
        return {}
    season = sorted(df["season"].unique())[-1]
    sub = df[df["season"] == season]
    out = {r["metric"]: r["value"] for _, r in sub.iterrows()}
    out["season"] = season
    return out


def headline() -> str | None:
    """One-line current-season summary for the Peru card, or None if uncached."""
    m = latest()
    if not m:
        return None
    total = m.get("season_total")
    yoy = m.get("yoy_growth")
    pk, pkv = m.get("peak_week"), m.get("peak_week_volume")
    bits = []
    if total:
        bits.append(f"{float(total)/1000:.0f}kt" + (f" ▲{float(yoy):.0f}%" if yoy else ""))
    if pk and pkv:
        bits.append(f"peak wk{int(pk)} {float(pkv)/1000:.0f}kt")
    return f"{m['season']} season (current): " + " · ".join(bits) if bits else None


if __name__ == "__main__":
    print(headline())
    print(load().to_string(index=False))
