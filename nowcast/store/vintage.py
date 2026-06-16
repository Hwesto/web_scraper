"""Append-only vintage store -- the spine of look-ahead-free back-testing.

A vintage is a snapshot of what a series looked like on a given date. Trade data
gets revised for over a year after first publication, and scraped signals only
exist from the day we start collecting. To avoid look-ahead bias the backtest
must read each series *as it stood at decision time*, never the latest revision.

Storage: one parquet file per (series, vintage_date) under data/vintages/<series>/.
Files are never overwritten -- a re-pull on the same day replaces only that day's
snapshot. ``as_of`` reconstructs the best-known value for each period using only
snapshots dated on or before the cutoff.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pandas as pd

from ..config import VINTAGE_DIR
from ..data.base import TIDY_COLUMNS


def _series_dir(series: str) -> Path:
    path = VINTAGE_DIR / series
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(frame: pd.DataFrame) -> Path | None:
    """Persist one tidy frame as the snapshot for its (series, vintage_date).

    The frame must be single-series, single-vintage (as produced by a
    SignalSource.fetch call). Returns the path written, or None if empty.
    """
    if frame.empty:
        return None
    series = frame["series"].iloc[0]
    vintage = frame["vintage_date"].iloc[0]
    if frame["series"].nunique() != 1 or frame["vintage_date"].nunique() != 1:
        raise ValueError("save() expects one series and one vintage_date per frame")
    out = _series_dir(series) / f"{vintage}.parquet"
    frame[TIDY_COLUMNS].to_parquet(out, index=False)
    return out


def _load_all(series: str) -> pd.DataFrame:
    files = sorted(_series_dir(series).glob("*.parquet"))
    if not files:
        return pd.DataFrame(columns=TIDY_COLUMNS)
    return pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)


def vintages(series: str) -> list[str]:
    """List available vintage dates (ISO strings) for a series."""
    return [f.stem for f in sorted(_series_dir(series).glob("*.parquet"))]


def as_of(series: str, cutoff: _dt.date) -> pd.DataFrame:
    """Best-known value per ref_period using only vintages <= cutoff.

    This is the function the backtest calls. For each period it keeps the value
    from the latest snapshot that existed at the cutoff, mirroring exactly what
    an analyst could have seen on that date.
    """
    frame = _load_all(series)
    if frame.empty:
        return frame
    cutoff_iso = cutoff.isoformat()
    visible = frame[frame["vintage_date"] <= cutoff_iso]
    if visible.empty:
        return pd.DataFrame(columns=TIDY_COLUMNS)
    visible = visible.sort_values("vintage_date")
    latest = visible.drop_duplicates(subset=["key", "ref_period"], keep="last")
    return latest.sort_values(["ref_period", "key"]).reset_index(drop=True)


def latest(series: str) -> pd.DataFrame:
    """Best-known value per ref_period across all vintages (today's view)."""
    return as_of(series, _dt.date.today())
