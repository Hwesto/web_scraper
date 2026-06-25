"""Guards for the within-month origin nowcast test.

The +12-18% edge only means something if the test (a) detects a real
contemporaneous signal and (b) invents none from noise.
"""
import numpy as np
import pandas as pd

from deep.backtest import within_month


def _seasonal(n=72, seed=0, noise=150.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="MS")
    t = np.arange(n)
    base = np.clip(1000 + 800 * np.sin(2 * np.pi * t / 12), 0, None)
    return pd.Series(base + rng.normal(0, noise, n), index=idx), base, idx


def test_detects_a_real_contemporaneous_signal():
    hmrc, _, _ = _seasonal()
    implied = hmrc.copy()                      # origin == import (perfect nowcast)
    r = within_month.run(transit_weeks=0, min_train=24, hmrc=hmrc, implied=implied)
    s = r["in_season"]["origin_nowcast"]
    assert s["skill_vs_snaive_%"] > 40         # must crush seasonal-naive
    assert s["dir_skill_%"] > 75


def test_no_skill_from_noise():
    hmrc, base, idx = _seasonal()
    rng = np.random.default_rng(2)
    implied = pd.Series(rng.uniform(0, 2000, len(idx)), index=idx)  # unrelated
    r = within_month.run(transit_weeks=0, min_train=24, hmrc=hmrc, implied=implied)
    assert r["in_season"]["origin_nowcast"]["dir_skill_%"] <= 65


def test_calibrated_run_picks_the_true_lag_out_of_sample():
    # HMRC seasonal; only transit=2 is the true contemporaneous signal, others noise.
    hmrc, _, idx = _seasonal(noise=120.0)
    rng = np.random.default_rng(5)
    implied = {0: pd.Series(rng.uniform(0, 2000, len(idx)), index=idx),
               2: hmrc.copy(),                                   # the real signal
               4: pd.Series(rng.uniform(0, 2000, len(idx)), index=idx)}
    cr = within_month.calibrated_run(min_train=24, transits=[0, 2, 4],
                                     hmrc=hmrc, implied_by_transit=implied)
    # OOS selection should favour the true lag and beat seasonal-naive.
    assert cr["transit_choices"].get(2, 0) > cr["transit_choices"].get(0, 0)
    assert cr["in_season"]["origin_nowcast"]["skill_vs_snaive_%"] > 20
