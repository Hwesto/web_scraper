"""Test the deep-sea shipment-shape wiring in the volume assembler."""
import numpy as np
import pandas as pd

from nowcast.volume import series


def test_shape_indicator_uses_transit_shifted_export(monkeypatch):
    # Fake export feed: 100 t in its first week, transit lag 2 weeks.
    idx = pd.date_range("2024-01-01", periods=4, freq="W-MON")
    exp = pd.Series([100.0, 0.0, 0.0, 0.0], index=idx)
    monkeypatch.setitem(series._EXPORT_FEEDS, "TestO",
                        (lambda fill_zeros=True: exp, 2))

    weeks = list(pd.date_range("2024-01-01", periods=8, freq="W-MON"))
    model_vol = np.full(8, 5.0)
    ind, mask = series._shape_indicator("TestO", weeks, model_vol, True)

    # export wk0 shifted +2 -> arrival at week index 2; coverage is weeks 2..5
    assert ind[2] == 100.0 and mask[2]
    assert mask[5] and not mask[1] and not mask[6]
    assert ind[0] == 5.0 and not mask[0]          # outside coverage -> model shape


def test_disabling_origin_export_falls_back_to_model():
    weeks = list(pd.date_range("2024-01-01", periods=4, freq="W-MON"))
    model_vol = np.full(4, 7.0)
    ind, mask = series._shape_indicator("Chile", weeks, model_vol, use_origin_export=False)
    assert (ind == 7.0).all() and not mask.any()
