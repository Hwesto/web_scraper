"""Retail price collector: JSON-LD parse + GBP/kg, offline (no network)."""
import datetime as dt

from nowcast.data import retail_price
from nowcast.data.retail_price import RetailBlueberryPrice, _parse


def _ld(name, price):
    return (f'<html><script type="application/ld+json">'
            f'{{"@type":"Product","name":"{name}","offers":{{"price":"{price}"}}}}'
            f'</script></html>')


def test_parse_reads_price_and_pack_size():
    assert _parse(_ld("Tesco Blueberries (150g)", "2.20")) == (2.20, 150.0)
    assert _parse(_ld("Big Blueberries (1kg)", "9.00")) == (9.00, 1000.0)
    # decodes HTML entities in the name
    assert _parse(_ld("Sainsbury&#039;s Blueberries (300g)", "3.30")) == (3.30, 300.0)


def test_parse_rejects_unusable():
    assert _parse("<html>no json-ld here</html>") is None
    assert _parse(_ld("Blueberries no size", "2.00")) is None      # no pack size
    assert _parse(_ld("Blueberries (150g)", "0")) is None          # non-positive price


def test_fetch_computes_gbp_per_kg_and_skips_failures(monkeypatch):
    canned = {  # url-suffix -> (price, grams), or None to simulate a skip
        "IBD496": (2.20, 150.0), "WMT802": (3.30, 300.0), "GDA152": (4.32, 500.0),
    }
    def fake(url):
        for sku, val in canned.items():
            if url.endswith(sku):
                return val
        return None                                    # everything else skipped
    monkeypatch.setattr(RetailBlueberryPrice, "_fetch_product", staticmethod(fake))
    monkeypatch.setattr(retail_price.time, "sleep", lambda *_: None)

    df = RetailBlueberryPrice().fetch(dt.date(2026, 6, 18))
    assert len(df) == 3                                # only the canned ones survive
    assert (df["ref_period"] == "2026-06-15").all()    # Monday of that week
    assert df["unit"].eq("gbp_per_kg").all()
    row = df[df["key"].str.endswith("150g")].iloc[0]
    assert abs(row["value"] - 2.20 / 0.150) < 1e-3     # £/kg (stored to 4dp)
    assert 8 < df["value"].median() < 20               # sane shelf level


def test_fetch_empty_when_all_fail(monkeypatch):
    monkeypatch.setattr(retail_price.time, "sleep", lambda *_: None)
    monkeypatch.setattr(RetailBlueberryPrice, "_fetch_product",
                        staticmethod(lambda url: None))
    assert RetailBlueberryPrice().fetch(dt.date(2026, 6, 18)).empty   # no faked rows


def test_fetch_aborts_politely_when_refused(monkeypatch):
    # collect one product, then the site refuses -> stop, keep what we had, no fake
    monkeypatch.setattr(retail_price.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def fake(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return (2.20, 150.0)
        raise retail_price._Refused("HTTP 403")
    monkeypatch.setattr(RetailBlueberryPrice, "_fetch_product", staticmethod(fake))

    df = RetailBlueberryPrice().fetch(dt.date(2026, 6, 18))
    assert len(df) == 1                                # kept the pre-block product
    assert calls["n"] == 2                             # stopped at the refusal, didn't pound on
