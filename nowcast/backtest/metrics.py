"""Scoring for the walk-forward backtest.

Accuracy (MAE/MAPE/RMSE) by lead time is the headline; directional skill is the
tradeable output; coverage checks the bands are honest.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_MAPE_FLOOR = 50.0  # tonnes; ignore MAPE on near-zero months (off-season noise)


def accuracy(actual: np.ndarray, pred: np.ndarray) -> dict:
    err = pred - actual
    out = {
        "n": int(len(actual)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
    }
    mask = actual > _MAPE_FLOOR
    out["mape"] = (
        float(np.mean(np.abs(err[mask] / actual[mask])) * 100.0) if mask.any() else np.nan
    )
    return out


def directional_skill(actual: np.ndarray, pred: np.ndarray, seasonal_norm: np.ndarray) -> float:
    """% of months the forecast calls the sign of the anomaly vs seasonal norm."""
    a_sign = np.sign(actual - seasonal_norm)
    p_sign = np.sign(pred - seasonal_norm)
    valid = a_sign != 0
    if not valid.any():
        return np.nan
    return float(np.mean(a_sign[valid] == p_sign[valid]) * 100.0)


def coverage(actual: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((actual >= lo) & (actual <= hi)) * 100.0)


def skill_vs(model_mae: float, bench_mae: float) -> float:
    """% MAE improvement of model over a benchmark (positive = better)."""
    if bench_mae == 0:
        return np.nan
    return (bench_mae - model_mae) / bench_mae * 100.0
