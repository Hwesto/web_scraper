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


def kalman_filter(
    y: np.ndarray,          # (T,) observations, np.nan where missing
    F_seq: list[np.ndarray],
    Q: np.ndarray,
    H: np.ndarray,          # (1, n) observation row used when y is present
    var_obs: float,
    x0: np.ndarray,
    P0: np.ndarray,
) -> FilterResult:
    T = len(y)
    n = x0.shape[0]
    x_filt = np.zeros((T, n)); P_filt = np.zeros((T, n, n))
    x_pred = np.zeros((T, n)); P_pred = np.zeros((T, n, n))
    loglik = 0.0

    x, P = x0.copy(), P0.copy()
    for t in range(T):
        # --- predict ---
        F = F_seq[t]
        x = F @ x
        P = F @ P @ F.T + Q
        P = 0.5 * (P + P.T)
        x_pred[t] = x; P_pred[t] = P

        # --- update (only if observed) ---
        if not np.isnan(y[t]):
            z = H @ x                       # (1,)
            S = H @ P @ H.T + var_obs       # (1,1)
            s = float(S[0, 0])
            innov = y[t] - float(z[0])
            K = (P @ H.T) / s               # (n,1)
            x = x + (K[:, 0] * innov)
            KH = K @ H
            ImKH = np.eye(n) - KH
            P = ImKH @ P @ ImKH.T + (K * var_obs) @ K.T
            P = 0.5 * (P + P.T)
            loglik += -0.5 * (_LOG2PI + np.log(s) + innov * innov / s)

        x_filt[t] = x; P_filt[t] = P

    return FilterResult(loglik, x_filt, P_filt, x_pred, P_pred)


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
