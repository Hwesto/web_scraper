"""Tests for the price layers (HMRC unit value + Chilean FOB)."""
from deep import price


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
    pos = usd[usd > 0]
    # bulk is a sane FOB level; rare late-season low-volume weeks can spike, so
    # check the median rather than every week.
    assert 3 < pos.median() < 12
    assert (pos > 1).all() and (pos.quantile(0.9) < 15)
    gbp = price.chile_fob_weekly(gbp=True)
    assert (gbp.dropna() < usd.reindex(gbp.index).dropna() + 1e-6).all()  # GBP < USD
