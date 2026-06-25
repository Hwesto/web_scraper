"""Guard for the origin-export turning-point test.

The negative result only means something if the test CAN detect a genuine lead.
This injects a synthetic world where import month M is exactly a scaled export
month M-1 (a perfect mechanical lead) and asserts odepa_lag1 then crushes
seasonal-naive. (Same principle as the price-fusion synthetic guard.)
"""
import numpy as np
import pandas as pd

from deep.backtest import lead


def _synthetic_lead(n=72, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="MS")
    t = np.arange(n)
    # Strong annual season + noise on the EXPORT series.
    exp = 1000 + 800 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 80, n)
    exp = np.clip(exp, 0, None)
    exp = pd.Series(exp, index=idx)
    # Import is exactly 0.9 * export shifted one month later (perfect lead).
    imp = 0.9 * exp.shift(1)
    imp.iloc[0] = 0.9 * exp.iloc[0]
    return imp, exp


def test_gauntlet_detects_a_real_lead():
    imp, exp = _synthetic_lead()
    r = lead.run(min_train=24, imp=imp, exp=exp)["in_season"]
    # With a perfect mechanical lead, lag1 must beat seasonal-naive on MAE...
    assert r["odepa_lag1"]["skill_vs_snaive_%"] > 30
    # ...and call turning points well above a coin flip.
    assert r["odepa_lag1"]["dir_skill_%"] > 70


def test_no_lead_when_export_is_pure_noise():
    # Sanity: unrelated export carries no turning-point skill.
    rng = np.random.default_rng(1)
    idx = pd.date_range("2018-01-01", periods=72, freq="MS")
    t = np.arange(72)
    imp = pd.Series(np.clip(1000 + 800 * np.sin(2 * np.pi * t / 12), 0, None), index=idx)
    exp = pd.Series(rng.uniform(0, 2000, 72), index=idx)
    r = lead.run(min_train=24, imp=imp, exp=exp)["in_season"]
    assert r["odepa_lag1"]["dir_skill_%"] <= 65    # no spurious turning-point skill
