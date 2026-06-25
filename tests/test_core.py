"""Core UK product — the two views + UK production (read committed data, no network)."""
from core import player_exports, uk_market, uk_production


def test_view1_into_uk():
    df = uk_market.into_uk()
    origins = set(df["origin"])
    assert {"Peru", "Morocco", "South Africa", "Chile"} <= origins   # the major players
    assert (df["share_pct"] > 0).all() and (df["cif_gbp_kg"] > 0).all()
    chile = df[df["origin"] == "Chile"].iloc[0]
    assert chile["variety"]                                          # Chile carries variety
    assert (df[df["origin"] != "Chile"]["variety"] == "").all()      # others blank (asymmetry)


def test_uk_supply_self_sufficiency():
    s = uk_market.uk_supply()
    assert s["imports_kt"] > 20                                      # UK imports tens of kt
    assert 0 < s["uk_production_kt"] < 20                            # grows a few kt
    assert s["self_sufficiency_pct"] < 20                            # small grower


def test_view2_player_exports():
    df = player_exports.load()
    if df.empty:
        return
    assert df["player"].nunique() >= 5
    for p, g in df.groupby("player"):
        assert 80 <= g["pct_tonnage"].sum() <= 120                  # shares ~ to 100 (min-vol tail dropped)
    sa = player_exports.by_player("South Africa")
    assert "United Kingdom" in set(sa["destination"])               # UK is SA's top market


def test_uk_production_sane():
    p = uk_production.load()
    if p.empty:
        return
    assert {"year", "production_kt"} <= set(p.columns)
    assert p["production_kt"].between(1, 20).all()


def test_board_data():
    from core import build_board as b
    cur, prev, rows, tot = b._board()
    assert rows and all(r["cif"] > 0 for r in rows)      # tickers have a price
    assert len(b._relay()) == 12                          # 12-month relay
    s = b._summary()
    assert s["imports_kt"] > 20 and 0 < s["ss"] < 20      # sane index strip
