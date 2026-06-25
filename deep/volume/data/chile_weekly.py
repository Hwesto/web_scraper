"""Loader for the cron-collected weekly Chile->UK blueberry export series.

The GitHub Actions workflow (.github/workflows/chile-weekly-exports.yml) writes
data/weekly/chile_uk_blueberry_weekly.csv (iso_week, net_kg) from the Aduana DUS
records on datos.gob.cl -- the free WEEKLY origin signal (validated against ODEPA
monthly to ~3%). This is the shipment-tier weekly SHAPE for the Chile deep-sea
leg of the Part 2 volume product, and the input to a within-month nowcast of the
HMRC/ODEPA monthly print (origin export leads arrival by transit time).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ...config import KG_PER_TONNE, REPO_ROOT

WEEKLY_CSV = REPO_ROOT / "data" / "weekly" / "chile_uk_blueberry_weekly.csv"


def _iso_week_start(iso_week: str) -> pd.Timestamp:
    year, wk = iso_week.split("-W")
    return pd.Timestamp.fromisocalendar(int(year), int(wk), 1)  # Monday


def load_weekly_exports(fill_zeros: bool = True, path: Path | None = None) -> pd.Series:
    """Weekly Chile->UK export (tonnes) indexed by ISO-week Monday.

    Off-season weeks are genuinely ~zero (austral counter-season); fill_zeros
    reindexes to a complete weekly grid so downstream benchmarking/nowcasting
    sees the gaps as 0, not missing.
    """
    csv = path or WEEKLY_CSV
    if not csv.exists():
        return pd.Series(dtype=float, name="chile_uk_export_t")
    df = pd.read_csv(csv)
    df["d"] = df["iso_week"].map(_iso_week_start)
    s = df.set_index("d")["net_kg"].sort_index() / KG_PER_TONNE
    s.name = "chile_uk_export_t"
    if fill_zeros and len(s):
        grid = pd.date_range(s.index.min(), s.index.max(), freq="W-MON")
        s = s.reindex(grid, fill_value=0.0)
    return s


def monthly_from_weekly(weekly: pd.Series | None = None) -> pd.Series:
    """Aggregate the weekly series to months (ISO week assigned by its Thursday),
    for the cross-check against ODEPA/HMRC monthly totals."""
    weekly = load_weekly_exports() if weekly is None else weekly
    if weekly.empty:
        return weekly
    # Each index is a Monday; assign the week to the month of its Thursday (+3d).
    months = weekly.index.to_series().apply(
        lambda d: (d + pd.Timedelta(days=3)).replace(day=1))
    return weekly.groupby(months).sum()


if __name__ == "__main__":
    s = load_weekly_exports()
    print(f"weeks: {len(s)}  range: {s.index.min()}..{s.index.max()}  total t: {s.sum():.0f}")
    print(s[s > 0].tail(8).round(1).to_string())
