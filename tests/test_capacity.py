"""Tests for the planting-age -> bearing-capacity model."""
import pandas as pd

from nowcast.farm import capacity


def test_yield_fraction_is_monotonic_and_bounded():
    fracs = [capacity.yield_fraction(a) for a in range(0, 8)]
    assert fracs[0] == 0.0
    assert all(b >= a for a, b in zip(fracs, fracs[1:]))   # non-decreasing
    assert capacity.yield_fraction(6) == 1.0 and capacity.yield_fraction(20) == 1.0


def test_bearing_capacity_ages_blocks():
    # One 100 ha block planted 2020: immature in 2021, fully bearing by 2026.
    blocks = pd.DataFrame([{"planting_year": 2020, "hectares": 100.0}])
    assert capacity.bearing_capacity(blocks, 2020) == 0.0           # age 0
    assert capacity.bearing_capacity(blocks, 2026) == 100.0          # age 6 -> full
    assert 0 < capacity.bearing_capacity(blocks, 2023) < 100.0       # age 3 -> partial


def test_capacity_trajectory_rises_as_block_matures():
    blocks = pd.DataFrame([{"planting_year": 2022, "hectares": 50.0}])
    traj = capacity.capacity_trajectory(blocks, range(2022, 2029))
    assert traj.is_monotonic_increasing
    assert traj.iloc[-1] == 50.0      # mature
