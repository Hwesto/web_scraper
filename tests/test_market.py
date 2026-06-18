"""Tests for the destination-economics layer (Comtrade + netback).

These read the committed cache (no network); the cron refreshes it. They assert the
shape and the load-bearing *relationships* (freight positive, the Asia premium
survives freight, the US is the volume sink), not exact prices that drift each year.
"""
import pandas as pd

from nowcast.market import comtrade, netback


def test_comtrade_cache_loads_and_is_sane():
    df = comtrade.load()
    assert len(df), "cache empty -- run python -m nowcast.market.comtrade"
    assert {"year", "destination", "cif_usd_kg", "net_kg", "value_usd"} <= set(df.columns)
    assert "United States" in set(df["destination"])
    assert (df["value_usd"] > 0).all() and (df["net_kg"] > 0).all()
    # tiny tail shipments give noisy unit values; check the commercially-sized lanes
    bulk = df[df["net_kg"] >= 200_000]["cif_usd_kg"]
    assert (bulk > 2).all() and (bulk < 15).all()              # plausible CIF USD/kg


def test_netback_subtracts_freight_and_ranks():
    t = netback.netback_table()
    assert len(t)
    # netback is strictly below CIF (freight is a positive deduction)
    assert (t["netback_usd_kg"] < t["cif_usd_kg"]).all()
    assert (t["freight_usd_kg"] > 0).all()
    # table is returned best-first
    assert t["netback_usd_kg"].is_monotonic_decreasing


def test_us_is_the_volume_sink():
    t = netback.netback_table().set_index("destination")
    assert "United States" in t.index
    # the US absorbs by far the most fruit -- the bulk lane
    assert t.loc["United States", "vol_share_%"] == t["vol_share_%"].max()
    assert t.loc["United States", "vol_share_%"] > 25


def test_asia_premium_survives_freight():
    # the headline finding: a premium Asian market nets more per kg than the US bulk
    # lane even after its longer, dearer voyage.
    t = netback.netback_table().set_index("destination")
    if "South Korea" in t.index and "United States" in t.index:
        assert t.loc["South Korea", "netback_usd_kg"] > t.loc["United States", "netback_usd_kg"]
        assert t.loc["South Korea", "transit_days"] > t.loc["United States", "transit_days"]
