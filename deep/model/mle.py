"""Maximum-likelihood calibration of the four noise variances.

The R/Q variances are the only "fusion weights" in the model. We estimate them
once by maximising the Kalman log-likelihood on a training window, then FREEZE
them for the out-of-sample backtest (no per-signal hand-tuning on test data).

Optimisation is over log-variances (unconstrained) with Nelder-Mead -- four
parameters, no gradients needed, robust.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from .kalman import kalman_filter
from .ssm import build_system


def _f_sequence(system, xi_seq):
    return [system.F(xi) for xi in xi_seq]


def neg_loglik(params, y, xi_seq, k, x0, P0) -> float:
    system = build_system(params, k)
    F_seq = _f_sequence(system, xi_seq)
    res = kalman_filter(y, F_seq, system.Q, system.H_hmrc, system.var_hmrc, x0, P0)
    if not np.isfinite(res.loglik):
        return 1e12
    return -res.loglik


def calibrate(y, xi_seq, k, x0, P0, init=None, maxiter=2000, hmrc_cv=0.03):
    """Return (best_params, neg_loglik) maximising the filter likelihood.

    HMRC observation noise is FIXED, not estimated: HMRC is the definitional
    monthly truth we disaggregate, so its only error is the week/month boundary
    approximation (~hmrc_cv of the monthly level). Estimating it lets the
    optimiser dump all variation into obs noise and collapse the dynamics
    (a known identifiability pile-up). We therefore fit only the 3 process
    variances and hold log_var_hmrc fixed.
    """
    obs = y[~np.isnan(y)]
    scale = max(float(np.nanmedian(obs)) if obs.size else 1.0, 1.0)
    log_var_hmrc = float(np.log((hmrc_cv * scale) ** 2))

    if init is None:
        init = np.log(np.array([
            (0.10 * scale) ** 2,   # level
            (0.02 * scale) ** 2,   # slope
            (0.10 * scale) ** 2,   # seasonal
        ]))

    def nll3(p3):
        return neg_loglik(np.append(p3, log_var_hmrc), y, xi_seq, k, x0, P0)

    result = minimize(
        nll3, np.asarray(init[:3], float),
        method="Nelder-Mead",
        options={"maxiter": maxiter, "xatol": 1e-4, "fatol": 1e-3},
    )
    return np.append(result.x, log_var_hmrc), result.fun
