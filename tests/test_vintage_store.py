"""Tests for the vintage store -- the look-ahead-free read path the backtest relies on.

The one piece of logic that MUST be correct: as_of(cutoff) returns, for each
period, the value from the latest snapshot dated on/before the cutoff -- and
never a future revision.
"""
import datetime as _dt

import pandas as pd
import pytest

from nowcast.data.base import TIDY_COLUMNS
from nowcast.store import vintage


def _row(series, ref_period, value, vintage_date, key=""):
    return {
        "series": series, "ref_period": ref_period, "freq": "M",
        "key": key, "value": value, "unit": "tonnes", "vintage_date": vintage_date,
    }


@pytest.fixture()
def seeded_store(tmp_path, monkeypatch):
    # Redirect the store to a temp dir so tests never touch real data.
    monkeypatch.setattr(vintage, "VINTAGE_DIR", tmp_path, raising=True)
    s = "demo"
    # First vintage: Jan provisional = 100.
    vintage.save(pd.DataFrame([_row(s, "2024-01-01", 100.0, "2024-03-01")])[TIDY_COLUMNS])
    # Later vintage: Jan revised up to 130, Feb first published = 80.
    vintage.save(pd.DataFrame([
        _row(s, "2024-01-01", 130.0, "2024-04-01"),
        _row(s, "2024-02-01", 80.0, "2024-04-01"),
    ])[TIDY_COLUMNS])
    return s


def test_as_of_sees_only_past_vintages(seeded_store):
    # On 2024-03-15 only the first vintage existed: Jan=100, no Feb yet.
    view = vintage.as_of(seeded_store, _dt.date(2024, 3, 15))
    assert dict(zip(view["ref_period"], view["value"])) == {"2024-01-01": 100.0}


def test_as_of_takes_latest_revision_within_cutoff(seeded_store):
    # After the April revision: Jan revised to 130, Feb appears at 80.
    view = vintage.as_of(seeded_store, _dt.date(2024, 5, 1))
    assert dict(zip(view["ref_period"], view["value"])) == {
        "2024-01-01": 130.0, "2024-02-01": 80.0,
    }


def test_as_of_never_leaks_future(seeded_store):
    # The revision is dated 2024-04-01; a cutoff just before must not see 130.
    view = vintage.as_of(seeded_store, _dt.date(2024, 3, 31))
    assert view.loc[view["ref_period"] == "2024-01-01", "value"].iloc[0] == 100.0
