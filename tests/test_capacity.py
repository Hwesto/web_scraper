"""Tests for the planting-age -> bearing-capacity model."""
import pandas as pd

from deep.farm import capacity


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


def test_variety_weight_discounts_old_soft_varieties():
    assert capacity.variety_weight("Brigitta") < 0.35       # old, soft -> frozen
    assert capacity.variety_weight("Blue Ribbon") > 0.8     # new, firm -> fresh
    assert capacity.variety_weight("Some Unknown") == 0.5   # default


def _multi_vintage():
    # Two comprehensive years (large area) + one partial-coverage year (tiny).
    rows = []
    for y, n in [(2019, 200), (2024, 150), (2023, 3)]:   # 2023 is partial
        for _ in range(n):
            rows.append({"survey_year": y, "region": "R", "variedad": "Duke",
                         "planting_year": 2010, "hectares": 50.0, "trees": 0})
    return pd.DataFrame(rows)


def test_comprehensive_years_excludes_partial_surveys():
    df = _multi_vintage()
    years = capacity.comprehensive_years(df, min_ha=1000.0)
    assert 2019 in years and 2024 in years
    assert 2023 not in years          # partial-coverage file must be excluded


def test_interpolated_capacity_is_bounded_by_anchors_no_coverage_artifact():
    # The fix: index must NOT swing to the partial-year's tiny value.
    df = _multi_vintage()
    cap = capacity.interpolated_capacity(df, range(2019, 2025), use_variety=False)
    lo, hi = cap.min(), cap.max()
    # 2019 anchor ~ 200*50=10000 mature; 2024 ~ 150*50=7500; all seasons between.
    assert 7000 <= lo and hi <= 10500           # smooth, within anchor range
    assert cap[2023] > 6000                       # not crushed to the partial survey
