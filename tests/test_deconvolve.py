"""Tests for Netherlands re-export de-convolution: mass must be conserved and
only deep-sea (counter-season) months may be reattributed.
"""
import numpy as np
import pandas as pd

from deep.volume.deconvolve import deconvolve_netherlands


def _frame():
    idx = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-07-01"])
    return pd.DataFrame(
        {"Netherlands": [100.0, 80.0, 60.0], "Peru": [300.0, 100.0, 0.0],
         "Chile": [100.0, 100.0, 0.0]}, index=idx)


def test_mass_is_conserved():
    df = _frame()
    out = deconvolve_netherlands(df, reexport_fraction=0.5)
    assert np.isclose(df.values.sum(), out.values.sum())


def test_only_deep_sea_months_change():
    df = _frame()
    out = deconvolve_netherlands(df, reexport_fraction=0.5)
    # July (month 7) is not a deep-sea month -> unchanged.
    assert out.loc["2024-07-01"].equals(df.loc["2024-07-01"])
    # January is -> Netherlands reduced, deep-sea origins increased.
    assert out.at[pd.Timestamp("2024-01-01"), "Netherlands"] < df.at[pd.Timestamp("2024-01-01"), "Netherlands"]
    assert out.at[pd.Timestamp("2024-01-01"), "Peru"] > df.at[pd.Timestamp("2024-01-01"), "Peru"]


def test_reattribution_is_pro_rata_to_deep_sea_share():
    df = _frame()
    out = deconvolve_netherlands(df, reexport_fraction=0.5)
    # Jan: NL 100 * 0.5 = 50 reattributed across Peru:Chile = 300:100 = 3:1.
    assert np.isclose(out.at[pd.Timestamp("2024-01-01"), "Peru"], 300 + 37.5)
    assert np.isclose(out.at[pd.Timestamp("2024-01-01"), "Chile"], 100 + 12.5)
