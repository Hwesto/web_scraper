"""Walk-forward vintage replay -- the backtest that proves or kills the model.

For each decision point (a training cut-off month) we train the structural model
and every benchmark on exactly the data available then, forecast h months ahead,
and later score against the eventually-known actual. Scoring is at MONTHLY
aggregation, where HMRC is the truth.

Vintage caveat (honest): true vintage replay needs the data as it stood at each
decision date. We only have one snapshot so far, so this runs on the latest
(revised) values -- an optimistic approximation. The read path goes through
vintage.as_of, so as snapshots accrue the same code becomes truly look-ahead-free.
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from ..benchmarks import BENCHMARKS, seasonal_naive
from ..model.structural import BlueberryStructuralModel
from ..store import vintage
from . import metrics


def load_origin_series(origin: str, start: str = "2022-01-01",
                       as_of: _dt.date | None = None, fill_zeros: bool = True) -> pd.Series:
    frame = (vintage.as_of("hmrc_blueberry_imports", as_of) if as_of
             else vintage.latest("hmrc_blueberry_imports"))
    sub = frame[frame["key"] == origin].copy()
    sub["d"] = pd.to_datetime(sub["ref_period"])
    s = sub.set_index("d")["value"].sort_index()
    s = s[s.index >= start]
    # Absent months mean no recorded imports (genuine off-season) -> 0. Filling
    # them is essential for a FAIR backtest: otherwise we only ever test the
    # high-volume in-season months and flatter the model (a selection bias that
    # produced a spurious +37% "win" before this fix).
    if fill_zeros and len(s):
        s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS"), fill_value=0.0)
    return s


def run_backtest(series: pd.Series, k: int = 2, horizons=(1, 2, 3),
                 min_train: int = 24, maxiter: int = 800) -> pd.DataFrame:
    """Return tidy per-forecast records across decision points and horizons."""
    series = series.sort_index()
    months = list(series.index)
    max_h = max(horizons)
    rows = []

    for i in range(min_train, len(months) - 1):
        train_end = months[i]
        train = series.iloc[: i + 1]
        try:
            model = BlueberryStructuralModel(k_harmonics=k, maxiter=maxiter).fit(train)
            fc = model.forecast(h_months=max_h).to_frame().set_index("month")
        except Exception:
            continue

        for h in horizons:
            target = train_end + pd.DateOffset(months=h)
            if target not in series.index:
                continue
            key = f"{target.year:04d}-{target.month:02d}"
            if key not in fc.index:
                continue
            actual = float(series.loc[target])
            rec = {
                "train_end": train_end.date().isoformat(),
                "target": key, "h": h, "actual": actual,
                "model": float(fc.loc[key, "mean"]),
                "lo80": float(fc.loc[key, "lo80"]), "hi80": float(fc.loc[key, "hi80"]),
                "lo95": float(fc.loc[key, "lo95"]), "hi95": float(fc.loc[key, "hi95"]),
                "seasonal_norm": seasonal_naive(train, h),
            }
            for name, fn in BENCHMARKS.items():
                rec[name] = float(fn(train, h))
            rows.append(rec)

    return pd.DataFrame(rows)


def summarize(preds: pd.DataFrame) -> pd.DataFrame:
    """Per-horizon accuracy, directional skill, coverage and skill vs benchmarks."""
    out = []
    for h, g in preds.groupby("h"):
        actual = g["actual"].values
        norm = g["seasonal_norm"].values
        model_acc = metrics.accuracy(actual, g["model"].values)
        row = {
            "h": int(h), "n": model_acc["n"],
            "model_mae": model_acc["mae"], "model_rmse": model_acc["rmse"],
            "model_mape": model_acc["mape"],
            "dir_skill_%": metrics.directional_skill(actual, g["model"].values, norm),
            "cov80_%": metrics.coverage(actual, g["lo80"].values, g["hi80"].values),
            "cov95_%": metrics.coverage(actual, g["lo95"].values, g["hi95"].values),
        }
        for name in BENCHMARKS:
            bench_mae = metrics.accuracy(actual, g[name].values)["mae"]
            row[f"{name}_mae"] = bench_mae
            row[f"skill_vs_{name}_%"] = metrics.skill_vs(model_acc["mae"], bench_mae)
        out.append(row)
    return pd.DataFrame(out).sort_values("h").reset_index(drop=True)
