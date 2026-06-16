"""Benchmark forecasters the model must beat. Seasonal-naive is THE gate.

Each takes a monthly training series (pd.Series indexed by month-start) and a
horizon h, and returns the point forecast for the h-th month ahead. All operate
on exactly the information the structural model is given, for a fair comparison.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def seasonal_naive(train: pd.Series, h: int) -> float:
    """Same month last year (the value 12 months before the target month)."""
    target = train.index.max() + pd.DateOffset(months=h)
    ref = target - pd.DateOffset(months=12)
    key = pd.Timestamp(ref.year, ref.month, 1)
    if key in train.index:
        return float(train.loc[key])
    return float(train.iloc[-12]) if len(train) >= 12 else float(train.iloc[-1])


def persistence(train: pd.Series, h: int) -> float:
    """Last observed month, carried forward."""
    return float(train.iloc[-1])


def arima(train: pd.Series, h: int) -> float:
    """HMRC-only seasonal ARIMA, (1,1,1)(0,1,1,12)."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    y = train.astype(float).values
    if len(y) < 26:  # not enough for seasonal differencing
        return seasonal_naive(train, h)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fit = SARIMAX(
                y, order=(1, 1, 1), seasonal_order=(0, 1, 1, 12),
                enforce_stationarity=False, enforce_invertibility=False,
            ).fit(disp=False)
            return float(max(fit.forecast(steps=h)[-1], 0.0))
        except Exception:
            return seasonal_naive(train, h)


BENCHMARKS = {"seasonal_naive": seasonal_naive, "persistence": persistence, "arima": arima}
