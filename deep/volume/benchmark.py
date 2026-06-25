"""Temporal benchmarking -- the core technique that marries a monthly control
total to a weekly indicator shape (spec section 4).

Proportional Denton (PFD): find weekly v_t that (a) sums within each month to
the HMRC control total Y_m exactly, and (b) follows the SHAPE of the indicator
x_t with minimal distortion. Formulated on the ratio z_t = v_t / x_t: minimise
the smoothness penalty sum (z_t - z_{t-1})^2 subject to the monthly-sum
constraints sum_{t in m} x_t z_t = Y_m, then v_t = x_t z_t. Solved as a KKT
linear system (small: weeks + months).

Only months that HAVE a control total are benchmarked here; the ragged edge
(recent months with no HMRC print yet) is handled by the nowcast in series.py.
"""
from __future__ import annotations

import numpy as np

_EPS = 1e-6


def denton_pfd(indicator: np.ndarray, week_month: list[str],
               monthly_totals: dict[str, float]) -> np.ndarray:
    """Proportional-Denton benchmark of a weekly indicator to monthly totals.

    indicator       : (T,) weekly indicator x_t (>0); the shape to preserve.
    week_month      : (T,) "YYYY-MM" each week belongs to.
    monthly_totals  : {"YYYY-MM": Y_m} control totals (a subset of the months).

    Returns v_t (T,) for the benchmarked span; weeks whose month has no control
    total are returned as NaN (the assembler fills them via the nowcast).
    """
    x = np.asarray(indicator, float).copy()
    x[x <= 0] = _EPS
    T = len(x)
    months = [m for m in dict.fromkeys(week_month) if m in monthly_totals]
    # Index only the weeks inside benchmarked months, contiguously.
    idx = [t for t in range(T) if week_month[t] in monthly_totals]
    if not idx:
        return np.full(T, np.nan)
    pos = {t: i for i, t in enumerate(idx)}
    n = len(idx)

    # Smoothness operator D (first differences across the kept weeks, but only
    # within the contiguous run so month-boundary joins are smoothed).
    D = np.zeros((n - 1, n))
    for i in range(n - 1):
        D[i, i] = -1.0
        D[i, i + 1] = 1.0
    DtD = D.T @ D + _EPS * np.eye(n)        # ridge for a unique solution

    # Constraint matrix A z = Y:  sum_{t in m} x_t z_t = Y_m
    M = len(months)
    A = np.zeros((M, n))
    Y = np.zeros(M)
    for j, m in enumerate(months):
        Y[j] = monthly_totals[m]
        for t in idx:
            if week_month[t] == m:
                A[j, pos[t]] = x[t]

    # KKT system [[2DtD, A^T],[A, 0]] [z; lambda] = [0; Y]
    KKT = np.zeros((n + M, n + M))
    KKT[:n, :n] = 2 * DtD
    KKT[:n, n:] = A.T
    KKT[n:, :n] = A
    rhs = np.concatenate([np.zeros(n), Y])
    sol = np.linalg.solve(KKT, rhs)
    z = sol[:n]

    v = np.full(T, np.nan)
    for t in idx:
        v[t] = x[t] * z[pos[t]]
    return v


def proportional(indicator: np.ndarray, week_month: list[str],
                 monthly_totals: dict[str, float]) -> np.ndarray:
    """Robust fallback: distribute each month's total across its weeks in
    proportion to the indicator (no boundary smoothing)."""
    x = np.asarray(indicator, float).copy()
    x[x <= 0] = _EPS
    v = np.full(len(x), np.nan)
    for m, Y in monthly_totals.items():
        wk = [t for t in range(len(x)) if week_month[t] == m]
        if not wk:
            continue
        s = sum(x[t] for t in wk)
        for t in wk:
            v[t] = Y * x[t] / s
    return v
