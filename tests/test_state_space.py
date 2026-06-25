"""Correctness tests for the cumulator state-space.

The make-or-break invariant: the accum state at a month-end week must equal the
exact sum of the weekly volumes (level + seasonal) since the month's reset. If
this holds, HMRC monthly = sum of weekly nowcasts, which is the whole point of
modelling in volume space.
"""
import datetime as _dt

import numpy as np

from deep.model.calendar import build_week_grid
from deep.model.ssm import build_system, state_dim


def _propagate(system, grid, x0):
    """Deterministic (no-noise) state propagation across the grid."""
    xs = np.zeros((len(grid), x0.shape[0]))
    x = x0.copy()
    for t in range(len(grid)):
        x = system.F(grid.xi[t]) @ x
        xs[t] = x
    return xs


def test_accum_equals_sum_of_weekly_volume():
    params = np.log(np.array([1.0, 1.0, 1.0, 1.0]))  # values irrelevant (no noise)
    system = build_system(params, k_harmonics=2)
    grid = build_week_grid(_dt.date(2023, 1, 1), _dt.date(2023, 6, 30))

    n = state_dim(2)
    x0 = np.zeros(n)
    x0[0] = 100.0      # level
    x0[1] = 0.5        # slope
    x0[2] = 30.0       # a1
    x0[4] = 10.0       # a2
    xs = _propagate(system, grid, x0)

    weekly_vol = xs @ system.h_vol
    # Walk months, summing weekly volume from each reset, compare to accum.
    running = 0.0
    for t in range(len(grid)):
        running = (running if grid.xi[t] else 0.0) + weekly_vol[t]
        assert np.isclose(xs[t, system.accum_idx], running, rtol=1e-9, atol=1e-6)
        if grid.is_month_end[t]:
            running_check = xs[t, system.accum_idx]
            assert running_check > 0


def test_reset_zeroes_carry_on_first_week_of_month():
    grid = build_week_grid(_dt.date(2023, 1, 1), _dt.date(2023, 4, 30))
    # Every month's first assigned week must reset (xi==0).
    for t in range(len(grid)):
        first_of_month = t == 0 or grid.month_key[t] != grid.month_key[t - 1]
        assert (grid.xi[t] == 0) == first_of_month


def test_seasonal_rotation_is_periodic():
    # A pure seasonal state should return near its start after ~52 weeks.
    params = np.log(np.array([1.0, 1.0, 1.0, 1.0]))
    system = build_system(params, k_harmonics=1)
    grid = build_week_grid(_dt.date(2023, 1, 1), _dt.date(2024, 12, 31))
    n = state_dim(1)
    x0 = np.zeros(n); x0[2] = 50.0  # a1
    xs = _propagate(system, grid, x0)
    a1 = xs[:, 2]
    # one year later the seasonal component is close to its initial value
    assert abs(a1[52] - a1[0]) < 5.0
