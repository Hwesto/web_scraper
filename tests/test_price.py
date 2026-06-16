"""Tests for the price layers (HMRC unit value + Chilean FOB)."""
from nowcast import price


def test_import_unit_value_by_origin_is_sane():
    uv = price.import_unit_value()                  # GBP/kg pivot by origin
    assert "Chile" in uv.columns and "Peru" in uv.columns
    chile = price.import_unit_value("Chile").dropna()
    assert len(chile) > 12
    assert 2 < chile.mean() < 15                    # plausible GBP/kg CIF


def test_chile_fob_weekly_loads_and_converts():
    usd = price.chile_fob_weekly()
    if usd.empty:                                   # FOB CSV not yet produced
        return
    assert (usd[usd > 0] > 1).all() and (usd[usd > 0] < 20).all()
    gbp = price.chile_fob_weekly(gbp=True)
    assert (gbp.dropna() < usd.reindex(gbp.index).dropna() + 1e-6).all()  # GBP < USD
