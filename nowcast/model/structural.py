"""Structural-time-series model API: fit a monthly origin series, nowcast/forecast.

Wraps the weekly state-space + cumulator + MLE into a simple interface:

    model = BlueberryStructuralModel(k_harmonics=1)
    model.fit(monthly_tonnes)          # pd.Series indexed by month-start date
    fc = model.forecast(h_months=3)    # mean + 80/95% bands per future month

The state evolves weekly; HMRC enters as a monthly cumulator observation. Weekly
volume is available via .weekly_volume() but is treated as an unvalidated by-
product until an in-season weekly signal exists to check it against.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .calendar import build_week_grid
from .kalman import kalman_filter, kalman_filter_multi, rts_smoother
from .mle import calibrate
from .ssm import build_system, state_dim

_Z80, _Z95 = 1.2815515594, 1.9599639845
_AVG_WEEKS_PER_MONTH = 365.25 / 84.0  # 12 months -> ~4.348 weeks each


@dataclass
class MonthlyForecast:
    months: list[str]
    mean: np.ndarray
    lo80: np.ndarray
    hi80: np.ndarray
    lo95: np.ndarray
    hi95: np.ndarray

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "month": self.months, "mean": self.mean,
            "lo80": self.lo80, "hi80": self.hi80,
            "lo95": self.lo95, "hi95": self.hi95,
        })


class BlueberryStructuralModel:
    def __init__(self, k_harmonics: int = 1, maxiter: int = 2000):
        self.k = k_harmonics
        self.maxiter = maxiter
        self.params_ = None
        self._grid = None
        self._system = None
        self._monthly = None
        self._price = None          # full price series (pd.Series, monthly)
        self._price_cal = None      # (alpha, beta, var_price) or None

    # -- internal: lay observations on the weekly grid --
    def _observation_vector(self, grid, monthly: pd.Series) -> np.ndarray:
        y = np.full(len(grid), np.nan)
        for period, value in monthly.items():
            key = f"{period.year:04d}-{period.month:02d}"
            idx = grid.index_of_month_end(key)
            if idx is not None:
                y[idx] = float(value)
        return y

    def _initial_state(self, monthly: pd.Series):
        n = state_dim(self.k)
        first = float(monthly.iloc[0])
        weekly_level = first / _AVG_WEEKS_PER_MONTH
        x0 = np.zeros(n)
        x0[0] = weekly_level
        # Diffuse but proper prior, scaled to the series.
        sc = max(weekly_level, 1.0)
        P0 = np.zeros((n, n))
        P0[0, 0] = (5 * sc) ** 2          # level
        P0[1, 1] = (sc) ** 2              # slope
        for k in range(1, self.k + 1):
            i = 2 + 2 * (k - 1)
            P0[i, i] = (5 * sc) ** 2
            P0[i + 1, i + 1] = (5 * sc) ** 2
        P0[n - 1, n - 1] = (20 * sc) ** 2  # accum
        return x0, P0

    def _calibrate_price(self, monthly: pd.Series, price: pd.Series):
        """OLS of price on contemporaneous monthly volume over the TRAINING
        window: price = alpha + beta*volume + eps. beta is expected negative
        (more supply -> lower price). Returns (alpha, beta, var_resid) or None
        if too little overlap. Uses only training months (no look-ahead)."""
        joined = pd.concat([monthly.rename("v"), price.rename("p")], axis=1).dropna()
        if len(joined) < 12:
            return None
        v = joined["v"].values.astype(float)
        p = joined["p"].values.astype(float)
        beta, alpha = np.polyfit(v, p, 1)
        resid = p - (alpha + beta * v)
        var_resid = float(np.var(resid)) or 1.0
        return float(alpha), float(beta), var_resid

    def fit(self, monthly: pd.Series, price: pd.Series | None = None, init=None
            ) -> "BlueberryStructuralModel":
        monthly = monthly.sort_index()
        self._monthly = monthly
        start = monthly.index.min().date()
        end = monthly.index.max().date() + _dt.timedelta(days=7)
        grid = build_week_grid(start, end)
        y = self._observation_vector(grid, monthly)
        x0, P0 = self._initial_state(monthly)

        self.params_, self._negll_ = calibrate(
            y, grid.xi, self.k, x0, P0, init=init, maxiter=self.maxiter)
        self._system = build_system(self.params_, self.k)
        self._grid, self._y, self._x0, self._P0 = grid, y, x0, P0

        if price is not None:
            self._price = price.sort_index()
            self._price_cal = self._calibrate_price(monthly, self._price)
        return self

    def nowcast(self, target_key: str, use_price: bool = True) -> tuple[float, float]:
        """Nowcast the monthly volume for 'YYYY-MM' from HMRC through the prior
        month plus (optionally) the contemporaneous price for the target month.

        Models HMRC's publication lag: the target month's HMRC print is NOT yet
        available, but its retail price IS. Returns (mean, sd) of accum_target.
        """
        target = pd.Timestamp(int(target_key[:4]), int(target_key[5:7]), 1)
        grid = build_week_grid(self._monthly.index.min().date(),
                               (target + pd.DateOffset(days=7)).date())
        S = self._system
        obs_seq: list[list[tuple]] = [[] for _ in range(len(grid))]

        # HMRC observations: only months strictly before the target (lagged).
        for period, value in self._monthly.items():
            if period >= target:
                continue
            idx = grid.index_of_month_end(f"{period.year:04d}-{period.month:02d}")
            if idx is not None:
                obs_seq[idx].append((S.H_hmrc.ravel(), float(value), S.var_hmrc, 0.0))

        # Price observations on accum (affine), up to and INCLUDING the target.
        if use_price and self._price is not None and self._price_cal is not None:
            alpha, beta, var_price = self._price_cal
            h_price = beta * S.H_hmrc.ravel()
            for period, pval in self._price.items():
                if period > target:
                    continue
                idx = grid.index_of_month_end(f"{period.year:04d}-{period.month:02d}")
                if idx is not None:
                    obs_seq[idx].append((h_price, float(pval), var_price, alpha))

        F_seq = [S.F(xi) for xi in grid.xi]
        res = kalman_filter_multi(obs_seq, F_seq, S.Q, self._x0, self._P0)
        idx = grid.index_of_month_end(target_key)
        mean = float((S.H_hmrc @ res.x_filt[idx])[0])
        var = float((S.H_hmrc @ res.P_filt[idx] @ S.H_hmrc.T)[0, 0])
        return max(mean, 0.0), float(np.sqrt(max(var, 0.0)))

    def _run(self, grid, y):
        F_seq = [self._system.F(xi) for xi in grid.xi]
        res = kalman_filter(y, F_seq, self._system.Q, self._system.H_hmrc,
                            self._system.var_hmrc, self._x0, self._P0)
        return res, F_seq

    def forecast(self, h_months: int = 3) -> MonthlyForecast:
        if self._system is None:
            raise RuntimeError("call fit() first")
        last = self._monthly.index.max()
        horizon_end = (last + pd.DateOffset(months=h_months + 1)).date()
        grid = build_week_grid(self._monthly.index.min().date(), horizon_end)
        y = self._observation_vector(grid, self._monthly)  # nan beyond history
        res, _ = self._run(grid, y)

        H = self._system.H_hmrc
        future_keys = [
            f"{(last + pd.DateOffset(months=m)).year:04d}-"
            f"{(last + pd.DateOffset(months=m)).month:02d}"
            for m in range(1, h_months + 1)
        ]
        months, mean, var = [], [], []
        for key in future_keys:
            idx = grid.index_of_month_end(key)
            if idx is None:
                continue
            m = float((H @ res.x_pred[idx])[0])
            v = float((H @ res.P_pred[idx] @ H.T)[0, 0])
            months.append(key); mean.append(max(m, 0.0)); var.append(max(v, 0.0))
        mean = np.array(mean); sd = np.sqrt(np.array(var))
        return MonthlyForecast(
            months=months, mean=mean,
            lo80=np.clip(mean - _Z80 * sd, 0, None), hi80=mean + _Z80 * sd,
            lo95=np.clip(mean - _Z95 * sd, 0, None), hi95=mean + _Z95 * sd,
        )

    def decompose(self) -> pd.DataFrame:
        """Smoothed weekly level, seasonal and volume over the fit window."""
        res, F_seq = self._run(self._grid, self._y)
        xs, _ = rts_smoother(res, F_seq)
        level = xs[:, 0]
        seasonal = np.zeros(len(xs))
        for k in range(1, self.k + 1):
            seasonal += xs[:, 2 + 2 * (k - 1)]
        return pd.DataFrame({
            "week": self._grid.weeks, "level": level,
            "seasonal": seasonal, "volume": level + seasonal,
        })
