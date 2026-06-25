"""Tests for the pure cert-layer logic (status inference + GGN attach)."""
import pandas as pd

from deep.farm import certs


def _producers():
    return pd.DataFrame({"producer": ["HORTIFRUT", "AGROBERRIES", "DOLE"],
                         "net_kg": [1524351.0, 660124.8, 367752.0]})


def test_uk_cert_status_tags_every_producer():
    out = certs.tag_uk_cert_status(_producers())
    assert (out["cert_status"] == "inferred_certified").all()
    assert out["cert_basis"].str.contains("GLOBALG.A.P.").all()
    assert out["ggn"].isna().all()                 # no GGN until supplied


def test_attach_ggns_joins_out_of_band_numbers_case_insensitively():
    out = certs.tag_uk_cert_status(_producers())
    out = certs.attach_ggns(out, {"hortifrut": "4049928000000", "Dole": "4049928111111"})
    by = out.set_index("producer")["ggn"]
    assert by["HORTIFRUT"] == "4049928000000"
    assert by["DOLE"] == "4049928111111"
    assert pd.isna(by["AGROBERRIES"])              # not supplied -> stays NA
