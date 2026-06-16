"""Correctness tests for temporal benchmarking.

The defining invariant (spec section 1): benchmarked weekly volumes must sum,
within each month, to the HMRC control total -- exactly. And the result must
follow the indicator's shape (a flat indicator => flat weekly split).
"""
import numpy as np

from nowcast.volume.benchmark import denton_pfd, proportional


def _grid(n_months=4, weeks_per_month=4):
    week_month, x = [], []
    rng = np.random.default_rng(0)
    for m in range(n_months):
        key = f"2024-{m+1:02d}"
        for _ in range(weeks_per_month):
            week_month.append(key)
            x.append(float(rng.uniform(50, 200)))   # arbitrary positive shape
    return week_month, np.array(x)


def test_denton_reconciles_to_control_totals_exactly():
    wm, x = _grid()
    totals = {"2024-01": 1000.0, "2024-02": 1500.0, "2024-03": 800.0, "2024-04": 1200.0}
    v = denton_pfd(x, wm, totals)
    for m, Y in totals.items():
        got = sum(v[t] for t in range(len(v)) if wm[t] == m)
        assert np.isclose(got, Y, rtol=1e-7), (m, got, Y)


def test_denton_preserves_flat_shape():
    # Single month + flat indicator => flat split (no boundary to smooth across).
    wm = ["2024-01"] * 4
    x = np.ones(len(wm))
    v = denton_pfd(x, wm, {"2024-01": 400.0})
    assert np.allclose(v, 100.0, atol=1e-3)     # 400 / 4 weeks


def test_denton_smooths_across_month_boundary():
    # Two months with different totals: the ratio ramps smoothly, so the last
    # week of the low month exceeds its flat share (this is Denton's value).
    wm = ["2024-01"] * 4 + ["2024-02"] * 4
    x = np.ones(len(wm))
    v = denton_pfd(x, wm, {"2024-01": 400.0, "2024-02": 800.0})
    assert np.isclose(sum(v[:4]), 400.0) and np.isclose(sum(v[4:]), 800.0)
    assert v[3] > v[0]                          # Jan ramps up toward Feb's level


def test_proportional_matches_indicator_ratio():
    wm = ["2024-01"] * 4
    x = np.array([1.0, 2.0, 3.0, 4.0])
    v = proportional(x, wm, {"2024-01": 100.0})
    assert np.allclose(v, np.array([10, 20, 30, 40.0]))


def test_unbenchmarked_months_are_nan():
    wm, x = _grid(3, 4)
    v = denton_pfd(x, wm, {"2024-01": 100.0})     # only month 1 has a total
    assert all(np.isnan(v[t]) for t in range(len(v)) if wm[t] != "2024-01")
    assert not any(np.isnan(v[t]) for t in range(len(v)) if wm[t] == "2024-01")
