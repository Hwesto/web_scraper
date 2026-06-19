"""Peru fundamentals from the USDA-FAS PSD table (offline; reads the committed CSV)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fetch_usda_peru as usda


def test_committed_peru_fundamentals_sane():
    df = usda.load()
    if df.empty:                                       # not fetched yet
        return
    assert {"season", "area_ha", "production_mt", "exports_mt",
            "exports_us_mt", "status"} <= set(df.columns)
    assert len(df) >= 4
    # exports below production, US a major-but-not-total share, sane area
    assert (df["exports_mt"] <= df["production_mt"]).all()
    assert df["exports_us_share_%"].between(40, 70).all()    # US dominance, not total
    assert df["area_ha"].between(5_000, 40_000).all()
    assert "forecast" in set(df["status"])                   # carries the forward view
