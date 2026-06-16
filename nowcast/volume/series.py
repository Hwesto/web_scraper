"""Assemble the reconciled weekly volume record (spec sections 4, 5, 8).

For one origin: HMRC monthly totals are the control; the Part 1 structural model
supplies the within-month weekly shape; Denton benchmarks the shape to the
control so monthly sums match exactly (aggregate_benchmarked tier); the ragged
edge past the last HMRC print is the model's weekly nowcast with bands (nowcast
tier). Output columns follow spec section 8.
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from ..backtest.replay import load_origin_series
from ..config import KG_PER_TONNE
from ..model.structural import BlueberryStructuralModel
from . import benchmark, tiering

_Z80 = 1.2815515594


def _iso_week(ts: pd.Timestamp) -> str:
    iso = ts.isocalendar()
    return f"{int(iso.year):04d}-W{int(iso.week):02d}"


def build_origin_volume(origin: str, k: int = 3, as_of: _dt.date | None = None,
                        start: str = "2022-01-01") -> pd.DataFrame:
    """Return the weekly volume record (kg) for one origin."""
    as_of = as_of or _dt.date.today()
    monthly = load_origin_series(origin, start=start, as_of=as_of)   # tonnes, zero-filled
    if monthly.empty:
        return pd.DataFrame()

    model = BlueberryStructuralModel(k_harmonics=k, maxiter=900).fit(monthly)
    path = model.weekly_volume_path(as_of)                           # week, volume, sd (tonnes)
    weeks = list(path["week"])
    week_month = [f"{w.year:04d}-{w.month:02d}" for w in weeks]
    indicator = path["volume"].clip(lower=0).values

    last_control = monthly.index.max()
    last_control_key = f"{last_control.year:04d}-{last_control.month:02d}"
    control = {f"{p.year:04d}-{p.month:02d}": float(v) for p, v in monthly.items()}

    benchmarked = benchmark.denton_pfd(indicator, week_month, control)

    recs = []
    for i, w in enumerate(weeks):
        wm = week_month[i]
        is_edge = wm > last_control_key
        if is_edge or np.isnan(benchmarked[i]):
            vol_t = max(float(indicator[i]), 0.0)
            tier, method = tiering.NOWCAST, tiering.M_NOWCAST
            ctrl = np.nan
        else:
            vol_t = float(benchmarked[i])
            tier, method = tiering.AGGREGATE_BENCHMARKED, tiering.M_ASSOC_BENCHMARKED
            ctrl = control[wm] * KG_PER_TONNE
        band = _Z80 * float(path["sd"].iloc[i]) * KG_PER_TONNE
        vol_kg = vol_t * KG_PER_TONNE
        recs.append({
            "origin_country": origin,
            "iso_week": _iso_week(w),
            "week_start": w.date().isoformat(),
            "volume_kg": round(vol_kg, 1),
            "confidence_tier": tier,
            "method": method,
            "source_refs": "HMRC-OTS;structural-model",
            "control_total_month_kg": round(ctrl, 1) if not np.isnan(ctrl) else np.nan,
            "band_low_kg": round(max(vol_kg - band, 0.0), 1),
            "band_high_kg": round(vol_kg + band, 1),
            "vintage_date": as_of.isoformat(),
        })
    return pd.DataFrame(recs)


def reconcile_error(volume: pd.DataFrame) -> pd.DataFrame:
    """Check benchmarked weekly sums equal their monthly control total (kg)."""
    bench = volume[volume["confidence_tier"] == tiering.AGGREGATE_BENCHMARKED].copy()
    bench["month"] = bench["week_start"].str[:7]
    g = bench.groupby("month").agg(weekly_sum=("volume_kg", "sum"),
                                   control=("control_total_month_kg", "first"))
    g["abs_err_kg"] = (g["weekly_sum"] - g["control"]).abs()
    return g
