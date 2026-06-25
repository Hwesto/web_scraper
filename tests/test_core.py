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
    cur, prev, rows, tot, mavg, mval = b._board()
    assert rows and all(r["cif"] > 0 for r in rows)      # tickers have a price
    assert tot > 0 and mavg > 0 and mval > 0              # month total + landed £/kg + £ spend
    assert "yoy" in rows[0]                               # year-on-year present
    assert abs(sum(r["share"] for r in rows) - 100) < 25  # shares ~sum to the month
    assert b._retail(cur) > 0                             # ONS proxy fallback resolves
    wk, shelf, per, n_packs = b._shelf()                  # real Trolley per-retailer shelf
    assert shelf > 0 and per and n_packs > 0 and all(p["med"] > 0 for p in per)
    insn = b._inseason_cif()                               # in-season per-origin landed
    assert insn and all(3 < c < 12 for _, c in insn)      # sane £/kg, no tiny-lane artefacts
    assert len(b._relay()) == 12                          # 12-month relay
    s = b._summary()
    assert s["imports_kt"] > 20 and 0 < s["ss"] < 20      # sane index strip
    assert s["imports_gbp_m"] > 100                        # trailing-year £m spend


def test_world_trade_sane():
    """Guard the Comtrade partner2 double-count fix on committed data."""
    from deep.market import comtrade_global as cg
    df = cg.load()
    if df.empty:
        return                                            # cache not built in this env
    imp = cg.top_importers(8, df)
    assert imp.iloc[0]["country"] == "United States"      # US is the clear #1
    uk = df[(df.role == "importer") & (df.country == "United Kingdom")]
    if not uk.empty:                                      # UK ~70kt; >150kt => double-count
        assert 40e6 < float(uk.iloc[0]["net_kg"]) < 150e6
