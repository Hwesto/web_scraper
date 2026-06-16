"""Structural state-space system for weekly blueberry volume.

State (K harmonics):  x = [level, slope, a_1, b_1, ..., a_K, b_K, accum]
  level, slope : local linear trend (absorbs Morocco's structural growth)
  a_k, b_k     : trig seasonal, angular freq w_k = 2*pi*k / WEEKS_PER_YEAR
  accum        : monthly cumulator of weekly volume (what HMRC observes)

Weekly volume readout:  v_t = level_t + sum_k a_k_t
Cumulator:              accum_t = xi_t * accum_{t-1} + v_t

Process noise has 3 free variances (parsimonious): level, slope, seasonal
(shared across harmonics). Observation noise: one variance for the monthly HMRC
read. All four are estimated by MLE (see mle.py) and frozen for the backtest.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .calendar import WEEKS_PER_YEAR

# Parameter vector layout (log-variances, optimised unconstrained):
PARAM_NAMES = ["log_var_level", "log_var_slope", "log_var_seas", "log_var_hmrc"]
N_PARAMS = len(PARAM_NAMES)


def state_dim(k_harmonics: int) -> int:
    return 2 + 2 * k_harmonics + 1


def _accum_index(k_harmonics: int) -> int:
    return state_dim(k_harmonics) - 1


@dataclass
class System:
    """Matrices for one parameter setting. F depends on the cumulator carry xi."""

    k: int
    F_carry: np.ndarray   # transition when xi=1 (mid-month week)
    F_reset: np.ndarray   # transition when xi=0 (first week of a month)
    Q: np.ndarray         # process noise covariance
    H_hmrc: np.ndarray    # observes accum
    h_vol: np.ndarray     # weekly volume readout (level + sum a_k)
    var_hmrc: float
    accum_idx: int

    def F(self, xi: int) -> np.ndarray:
        return self.F_carry if xi else self.F_reset


def _omega(k: int) -> float:
    return 2.0 * np.pi * k / WEEKS_PER_YEAR


def build_system(params: np.ndarray, k_harmonics: int = 1) -> System:
    """Build the System for the given log-variance parameter vector."""
    var_level, var_slope, var_seas, var_hmrc = np.exp(np.asarray(params, float))
    n = state_dim(k_harmonics)
    acc = _accum_index(k_harmonics)

    # --- transition (xi=1 carry version) ---
    F = np.zeros((n, n))
    F[0, 0] = 1.0; F[0, 1] = 1.0          # level' = level + slope
    F[1, 1] = 1.0                          # slope' = slope
    for k in range(1, k_harmonics + 1):
        i = 2 + 2 * (k - 1)
        c, s = np.cos(_omega(k)), np.sin(_omega(k))
        F[i, i] = c;      F[i, i + 1] = s
        F[i + 1, i] = -s; F[i + 1, i + 1] = c
    # accum row: accum_t = xi*accum_{t-1} + level_t + sum a_k_t
    F[acc, 0] = 1.0      # level_{t-1}
    F[acc, 1] = 1.0      # slope_{t-1} (enters level_t)
    for k in range(1, k_harmonics + 1):
        i = 2 + 2 * (k - 1)
        c, s = np.cos(_omega(k)), np.sin(_omega(k))
        F[acc, i] = c       # a_k_{t-1} -> a_k_t
        F[acc, i + 1] = s   # b_k_{t-1} -> a_k_t
    F[acc, acc] = 1.0    # carry

    F_carry = F.copy()
    F_reset = F.copy()
    F_reset[acc, acc] = 0.0  # reset cumulator on first week of month

    # --- process noise via loading matrix G ---
    # shocks: [eta_level, eta_slope, eta_a1, eta_b1, ...]; accum gets level + a_k shocks
    n_shocks = 2 + 2 * k_harmonics
    G = np.zeros((n, n_shocks))
    G[0, 0] = 1.0          # level
    G[1, 1] = 1.0          # slope
    G[acc, 0] = 1.0        # accum picks up level shock (accum includes level_t)
    var_vec = np.zeros(n_shocks)
    var_vec[0] = var_level
    var_vec[1] = var_slope
    for k in range(1, k_harmonics + 1):
        i = 2 + 2 * (k - 1)              # state index of a_k
        sa, sb = 2 + 2 * (k - 1), 3 + 2 * (k - 1)  # shock indices
        G[i, sa] = 1.0
        G[i + 1, sb] = 1.0
        G[acc, sa] = 1.0                 # accum includes a_k_t
        var_vec[sa] = var_seas
        var_vec[sb] = var_seas
    Q = G @ np.diag(var_vec) @ G.T

    H_hmrc = np.zeros((1, n)); H_hmrc[0, acc] = 1.0
    h_vol = np.zeros(n); h_vol[0] = 1.0
    for k in range(1, k_harmonics + 1):
        h_vol[2 + 2 * (k - 1)] = 1.0     # + a_k

    return System(
        k=k_harmonics, F_carry=F_carry, F_reset=F_reset, Q=Q,
        H_hmrc=H_hmrc, h_vol=h_vol, var_hmrc=float(var_hmrc), accum_idx=acc,
    )
