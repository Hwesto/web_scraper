"""Phyto-access x netback: who can chase the Asia premium.

Validates the matching + premium logic now, against a synthetic roster, so it is
proven independently of when the real SAG China orchard list lands via the cron.
"""
import pandas as pd

from nowcast.market import asia_access


def _roster(tmp_path):
    # a few names that should match our real producers + decoys that must not
    df = pd.DataFrame({
        "predio_name": ["HORTIFRUT CHILE S.A.", "AGROBERRIES LTDA", "SAN RAFAEL",
                        "EMPRESA FANTASMA XYZ", "OTRA COSA SPA"],
        "csg": ["CSG-1", "CSG-2", "CSG-3", "CSG-9", "CSG-8"],
        "region": [6, 6, 6, 1, 1],
    })
    p = tmp_path / "roster.csv"
    df.to_csv(p, index=False)
    return p


def test_asia_premium_is_positive_and_sane():
    prem = asia_access.asia_premium_usd_kg()
    # Asia nets more than the US bulk lane, but it's a per-kg premium not a fortune
    assert 0.2 < prem < 4.0


def test_ranked_matches_real_producers_and_flags_access(tmp_path):
    r = asia_access.ranked(_roster(tmp_path))
    assert len(r)
    approved = set(r.loc[r["china_approved"], "producer"])
    assert {"HORTIFRUT", "AGROBERRIES"} <= approved      # real names matched
    # prize accrues only to approved producers, scaled by their volume
    assert (r.loc[~r["china_approved"], "prize_usd"] == 0).all()
    assert (r.loc[r["china_approved"], "prize_usd"] > 0).all()


def test_summary_degrades_without_roster(tmp_path):
    s = asia_access.summary(tmp_path / "does_not_exist.csv")
    assert s["available"] is False
    assert "asia_premium_usd_kg" in s                    # still reports the premium
