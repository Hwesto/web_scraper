"""Per-origin export price (Comtrade, all reporters). Committed-table sanity +
offline parse test of the World/UK extraction."""
from nowcast.market import origin_prices


def test_committed_table_is_sane():
    df = origin_prices.load()
    if df.empty:                                    # not fetched yet
        return
    assert set(origin_prices._COLS) == set(df.columns)
    assert set(df["dest"]) <= {"World", "United Kingdom"}
    assert {"Chile", "South Africa"} <= set(df["origin"])
    assert df["fob_usd_kg"].between(1, 20).all()    # plausible blueberry FOB USD/kg


def test_wedge_brackets_freight():
    w = origin_prices.wedge()
    if w.empty:                                     # needs both feeds present
        return
    assert {"origin", "fob_gbp_kg", "cif_gbp_kg", "wedge_gbp_kg"} <= set(w.columns)
    assert (w["fob_gbp_kg"] > 0).all() and (w["cif_gbp_kg"] > 0).all()
    assert w["wedge_gbp_kg"].between(-3, 3).all()   # freight-scale, incl. re-export negatives
    if "Chile" in set(w["origin"]):                 # deep-sea: positive freight wedge
        assert w.set_index("origin").loc["Chile", "wedge_gbp_kg"] > 0


def test_refresh_extracts_world_and_uk(monkeypatch, tmp_path):
    # one reporter, canned partner rows: World(0), UK(826), and an ignored one
    monkeypatch.setattr(origin_prices, "ORIGINS", {152: "Chile"})
    monkeypatch.setattr(origin_prices, "CACHE", tmp_path / "out.csv")
    monkeypatch.setattr(origin_prices.time, "sleep", lambda *_: None)

    def fake_fetch(reporter, year, retries=4):
        return [
            {"partnerCode": 0, "primaryValue": 1_000_000.0, "netWgt": 200_000.0},
            {"partnerCode": 826, "primaryValue": 530_000.0, "netWgt": 100_000.0},
            {"partnerCode": 842, "primaryValue": 9_999.0, "netWgt": 1_000.0},  # USA, dropped
        ]
    monkeypatch.setattr(origin_prices, "_fetch", fake_fetch)

    df = origin_prices.refresh([2025])
    assert set(df["dest"]) == {"World", "United Kingdom"}      # only the two we track
    uk = df[df["dest"] == "United Kingdom"].iloc[0]
    assert uk["fob_usd_kg"] == 5.30                            # 530000 / 100000
    world = df[df["dest"] == "World"].iloc[0]
    assert world["fob_usd_kg"] == 5.0                          # 1e6 / 2e5
