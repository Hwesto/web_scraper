"""Tests for the cron-collected weekly Chile->UK export loader."""
import pandas as pd

from deep.volume.data import chile_weekly


def _write(tmp_path):
    csv = tmp_path / "wk.csv"
    csv.write_text("iso_week,net_kg\n2024-W01,100000\n2024-W02,200000\n2024-W05,50000\n")
    return csv


def test_load_parses_iso_week_to_monday_and_tonnes(tmp_path):
    s = chile_weekly.load_weekly_exports(fill_zeros=False, path=_write(tmp_path))
    assert s.loc[pd.Timestamp.fromisocalendar(2024, 1, 1)] == 100.0   # kg -> tonnes
    assert s.index.min() == pd.Timestamp.fromisocalendar(2024, 1, 1)  # Monday


def test_fill_zeros_completes_the_weekly_grid(tmp_path):
    s = chile_weekly.load_weekly_exports(fill_zeros=True, path=_write(tmp_path))
    # W01..W05 -> 5 contiguous weeks, the gap (W03,W04) filled with 0.
    assert len(s) == 5
    assert (s == 0).sum() == 2


def test_monthly_aggregation_assigns_week_by_its_thursday(tmp_path):
    s = chile_weekly.load_weekly_exports(fill_zeros=False, path=_write(tmp_path))
    m = chile_weekly.monthly_from_weekly(s)
    # W01+W02 -> Jan; W05's Thursday is 2024-02-01 -> Feb (not Jan).
    assert m.loc[pd.Timestamp(2024, 1, 1)] == 300.0
    assert m.loc[pd.Timestamp(2024, 2, 1)] == 50.0
