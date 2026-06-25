"""Linear-Gaussian Kalman filter + RTS smoother with ragged (missing) obs.

Time-varying transition (the cumulator carry xi switches F each week) and a
scalar observation that is present only on month-end weeks (HMRC). Missing weeks
simply skip the update -- which is exactly what produces wider bands for recent,
not-yet-printed weeks and tighter bands once HMRC lands.

Numerics: symmetric covariance updates (Joseph form) to keep P positive
semidefinite over long weekly runs.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_LOG2PI = np.log(2.0 * np.pi)


@dataclass
class FilterResult:
    loglik: float
    x_filt: np.ndarray      # (T, n) filtered state means
    P_filt: np.ndarray      # (T, n, n) filtered covariances
    x_pred: np.ndarray      # (T, n) one-step-ahead predicted means
    P_pred: np.ndarray      # (T, n, n) predicted covariances


def _scalar_update(x, P, h, value, var, offset, n):
    """One scalar Kalman update for obs value = h.x + offset + N(0,var). Returns
    (x, P, loglik_contribution)."""
    z = float(h @ x) + offset
    Ph = P @ h                          # (n,)
    s = float(h @ Ph) + var
    innov = value - z
    K = Ph / s                          # (n,)
    x = x + K * innov
    ImKH = np.eye(n) - np.outer(K, h)
    P = ImKH @ P @ ImKH.T + np.outer(K, K) * var
    P = 0.5 * (P + P.T)
    ll = -0.5 * (_LOG2PI + np.log(s) + innov * innov / s)
    return x, P, ll


def kalman_filter_multi(
    obs_seq: list[list[tuple]],   # per t: list of (h (n,), value, var, offset)
    F_seq: list[np.ndarray],
    Q: np.ndarray,
    x0: np.ndarray,
    P0: np.ndarray,
) -> FilterResult:
    """Filter with an arbitrary set of scalar observations each step, applied
    sequentially. Missing streams simply contribute no tuple that step."""
    T = len(F_seq)
    n = x0.shape[0]
    x_filt = np.zeros((T, n)); P_filt = np.zeros((T, n, n))
    x_pred = np.zeros((T, n)); P_pred = np.zeros((T, n, n))
    loglik = 0.0

    x, P = x0.copy(), P0.copy()
    for t in range(T):
        F = F_seq[t]
        x = F @ x
        P = F @ P @ F.T + Q
        P = 0.5 * (P + P.T)
        x_pred[t] = x; P_pred[t] = P

        for h, value, var, offset in obs_seq[t]:
            x, P, ll = _scalar_update(x, P, np.asarray(h, float), value, var, offset, n)
            loglik += ll

        x_filt[t] = x; P_filt[t] = P

    return FilterResult(loglik, x_filt, P_filt, x_pred, P_pred)


def kalman_filter(
    y: np.ndarray,          # (T,) observations, np.nan where missing
    F_seq: list[np.ndarray],
    Q: np.ndarray,
    H: np.ndarray,          # (1, n) observation row used when y is present
    var_obs: float,
    x0: np.ndarray,
    P0: np.ndarray,
) -> FilterResult:
    """Single-stream convenience wrapper over kalman_filter_multi."""
    h = np.asarray(H, float).ravel()
    obs_seq = [
        ([] if np.isnan(y[t]) else [(h, float(y[t]), var_obs, 0.0)])
        for t in range(len(y))
    ]
    return kalman_filter_multi(obs_seq, F_seq, Q, x0, P0)


def rts_smoother(res: FilterResult, F_seq: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Rauch-Tung-Striebel backward pass -> smoothed means/covariances."""
    T, n = res.x_filt.shape
    xs = res.x_filt.copy(); Ps = res.P_filt.copy()
    for t in range(T - 2, -1, -1):
        F = F_seq[t + 1]
        Ppred = res.P_pred[t + 1]
        # Jitter keeps the solve stable when process noise is ~0 on some states
        # (deterministic trend/seasonal make P_pred near-singular).
        jit = 1e-8 * (np.trace(Ppred) / Ppred.shape[0] + 1.0)
        Ppred_j = Ppred + jit * np.eye(Ppred.shape[0])
        # J = P_filt[t] F^T P_pred[t+1]^{-1}
        J = np.linalg.solve(Ppred_j, F @ res.P_filt[t]).T
        xs[t] = res.x_filt[t] + J @ (xs[t + 1] - res.x_pred[t + 1])
        Ps[t] = res.P_filt[t] + J @ (Ps[t + 1] - Ppred) @ J.T
        Ps[t] = 0.5 * (Ps[t] + Ps[t].T)
    return xs, Ps
