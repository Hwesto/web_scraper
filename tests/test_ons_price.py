"""ONS retail price splice: direct blueberry GBP/kg + post-2025 proxy extension.

Offline -- builds tiny xlsx fixtures and monkeypatches the network, so the splice
logic is pinned without hitting ONS/GitHub.
"""
import io

import pandas as pd
import pytest

from deep.data import ons_price
from deep.data.ons_price import OnsRetailBlueberryPrice


def _old_xlsx() -> bytes:
    buf = io.BytesIO()
    meta = pd.DataFrame({"ITEM_ID": [9001], "ITEM_DESC": ["Blueberries, per kg"]})
    cols = pd.to_datetime(["2024-11-01", "2024-12-01", "2025-01-01"])
    avg = pd.DataFrame([[9001, 12.0, 12.2, 12.46]], columns=["ITEM_ID", *cols])
    with pd.ExcelWriter(buf) as w:
        meta.to_excel(w, sheet_name="metadata", index=False)
        avg.to_excel(w, sheet_name="averageprice", index=False)
    return buf.getvalue()


def _new_xlsx(anchor_index=100.0) -> bytes:
    buf = io.BytesIO()
    cols = pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"])
    # all-berries chained index: 100 at anchor, +5% then -2%
    chained = pd.DataFrame([[ons_price._BERRIES_SEGMENT, anchor_index,
                             anchor_index * 1.05, anchor_index * 1.03]],
                           columns=["ITEM_ID", *cols])
    with pd.ExcelWriter(buf) as w:
        chained.to_excel(w, sheet_name="chained", index=False)
    return buf.getvalue()


def _patch(monkeypatch, new_bytes):
    def fake_get(url):
        if url == ons_price._URL_OLD:
            return _old_xlsx()
        if new_bytes is None:
            raise RuntimeError("new feed unreachable")
        return new_bytes
    monkeypatch.setattr(OnsRetailBlueberryPrice, "_get", staticmethod(fake_get))


def test_splice_extends_and_flags_proxy(monkeypatch):
    _patch(monkeypatch, _new_xlsx())
    df = OnsRetailBlueberryPrice().fetch()
    direct = df[df["key"] == ""]
    proxy = df[df["key"] == "proxy_berries_index"]

    # direct ends at the anchor; proxy picks up strictly after it (no overlap)
    assert direct["ref_period"].max() == "2025-01-01"
    assert proxy["ref_period"].min() == "2025-02-01"
    assert "2025-01-01" not in set(proxy["ref_period"])

    # splice math: anchor £12.46 carried forward by the +5% index step
    feb = proxy.set_index("ref_period").loc["2025-02-01", "value"]
    assert feb == pytest.approx(12.46 * 1.05, rel=1e-6)
    # continuous level (no jump) at the join
    assert direct.set_index("ref_period").loc["2025-01-01", "value"] == pytest.approx(12.46)


def test_degrades_to_direct_only_when_new_feed_down(monkeypatch):
    _patch(monkeypatch, None)                       # new feed raises
    df = OnsRetailBlueberryPrice().fetch()
    assert (df["key"] == "").all()                  # no proxy rows faked
    assert df["ref_period"].max() == "2025-01-01"
    assert len(df) == 3
