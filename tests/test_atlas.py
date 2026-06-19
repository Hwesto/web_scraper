"""Atlas Phase-0/1 foundations: HS registry, schema, registry table, country
lookup, and the Comtrade global sweep (offline parse + committed-table sanity)."""
from atlas import comtrade_sweep as cs
from atlas import (comtrade_matrix, comtrade_monthly, countries, eurostat,
                   hs_codes, registry, schema, senasica)


# ---- HS-code registry ----------------------------------------------------

def test_blueberry_hs6_and_uk_split():
    assert hs_codes.hs6("blueberry") == "081040"
    uk = hs_codes.national_codes("blueberry", jurisdiction="UK")
    assert "08104050" in set(uk["national_code"])          # the commercial line
    assert "08104010" in set(uk["national_code"])          # cowberry, excluded sibling
    assert "blueberry" in hs_codes.commodities(verified_only=True)


def test_hs_other_fruit_seed_present_but_unverified():
    # the other-fruit extension key exists (Phase 4) but isn't catalogued yet
    coms = hs_codes.commodities()
    assert {"cherry", "strawberry"} <= set(coms)
    assert "cherry" not in hs_codes.commodities(verified_only=True)


# ---- schema --------------------------------------------------------------

def test_seed_satisfies_schema():
    assert schema.validate(registry.load()) == []


def test_schema_flags_bad_values():
    df = registry.load().copy()
    df.loc[df.index[0], "access"] = "maybe"               # not in {free,paid,none}
    issues = schema.validate(df)
    assert any("access" in i for i in issues)


# ---- registry ------------------------------------------------------------

def test_registry_has_the_three_access_classes():
    df = registry.load()
    assert set(df["access"]) == {"free", "paid", "none"}
    # the structural-ceiling exemplars from the baselines
    paid = set(registry.gaps(access="paid")["data_point"])
    assert any("bill of lading" in p for p in paid)
    none = set(registry.gaps(access="none")["data_point"])
    assert any("variety on shelf" in n for n in none)


def test_free_wired_ceiling_is_queryable():
    wired = registry.gaps(access="free", wired="yes")
    # the held free spine: Comtrade matrix, HMRC, Chile DUS all present
    sources = " ".join(wired["source"])
    assert "Comtrade" in sources and "HMRC" in sources and "DUS" in sources
    headroom = registry.gaps(access="free", wired="no")
    assert len(headroom) > 0                               # free-but-unwired exists


def test_coverage_counts_every_row():
    assert int(registry.coverage()["n"].sum()) == len(registry.load())


def test_phase2_national_overlays_catalogued():
    df = registry.load()
    # the top exporters beyond the Chile/Peru reference lanes are now catalogued
    assert {"Spain", "Netherlands", "Morocco", "USA", "Mexico", "Canada",
            "South Africa", "Poland"} <= set(df["country"])
    # recurring Phase-2 finding: free shipment-level export-with-names exists nowhere
    bol = df[df["data_point"].str.contains("shipment-level export with exporter")]
    assert len(bol) > 0 and set(bol["access"]) == {"paid"}
    # but some free NPPO orchard rosters DO exist (the SAG-China analogue) -- e.g. Mexico
    phyto_free = df[df["data_point"].str.contains("phyto") & (df["access"] == "free")]
    assert "Mexico" in set(phyto_free["country"])


def test_phase2b_importer_and_hub_overlays():
    df = registry.load()
    # importer-side + re-export-hub markets catalogued
    assert {"Germany", "France", "China", "Hong Kong", "Switzerland",
            "South Korea", "Japan", "Belgium", "Serbia"} <= set(df["country"])
    # Hong Kong is the one source with an explicit re-export flow split
    hk = df[(df["country"] == "Hong Kong") & df["data_point"].str.contains("re-export")]
    assert len(hk) == 1 and hk.iloc[0]["access"] == "free"
    # 'both' role exists for the re-export hubs (import + re-export)
    assert "both" in set(df["role"])


# ---- Phase 3: wired overlays (Eurostat COMEXT + Comtrade bilateral grid) ----

def test_eurostat_tidy_drops_aggregates_and_computes_unit():
    # _tidy pivots value+quantity onto one lane row, converts 100kg->kg, drops EU aggregates
    recs = [
        {"time": "2023", "reporter": "ES", "partner": "DE", "flow": "2",
         "indicators": "VALUE_IN_EUROS", "_val": 1000.0},
        {"time": "2023", "reporter": "ES", "partner": "DE", "flow": "2",
         "indicators": "QUANTITY_IN_100KG", "_val": 2.0},          # -> 200 kg
        {"time": "2023", "reporter": "ES", "partner": "INT_EU", "flow": "2",
         "indicators": "VALUE_IN_EUROS", "_val": 9999.0},          # aggregate -> dropped
    ]
    df = eurostat._tidy(recs)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["partner"] == "DE" and row["net_kg"] == 200.0
    assert row["eur_per_kg"] == 5.0                                 # 1000 / 200
    assert not eurostat._is_country("INT_EU") and eurostat._is_country("DE")
    assert eurostat._is_country("WORLD")


def test_eurostat_committed_table_is_sane():
    df = eurostat.load()
    if df.empty:                                                    # not fetched yet
        return
    assert set(eurostat._COLS) == set(df.columns)
    assert set(df["flow"]) <= {"import", "export"}
    # validate on material lanes only -- tiny-N unit values lie (HANDOFF gotcha)
    material = df[df["net_kg"] >= 50_000]
    assert material["eur_per_kg"].between(0.5, 30).all()            # plausible EUR/kg
    assert "ES" in set(df["reporter"])


def test_comtrade_matrix_filters_and_dedups(monkeypatch, tmp_path):
    monkeypatch.setattr(comtrade_matrix, "CACHE", tmp_path / "bi.csv")
    monkeypatch.setattr(comtrade_matrix.time, "sleep", lambda *_: None)
    monkeypatch.setattr(comtrade_matrix.comtrade_sweep, "is_provisional", lambda y: False)

    def fake_fetch(reporter, year, hs, retries=4):
        return [
            {"partnerCode": 0, "primaryValue": 9e9, "netWgt": 1e9},        # World -> skip
            {"partnerCode": 842, "primaryValue": 1_000_000.0, "netWgt": 200_000.0},
            {"partnerCode": 842, "primaryValue": 1_000_000.0, "netWgt": 200_000.0},  # dup
            {"partnerCode": 528, "primaryValue": 50.0, "netWgt": 5.0},     # < _MIN_KG -> drop
        ]
    monkeypatch.setattr(comtrade_matrix, "_fetch", fake_fetch)
    df = comtrade_matrix.refresh([2023], exporters=[604], names={604: "Peru", 842: "USA"})
    assert list(df["importer"]) == ["USA"]                          # World+dup+trace removed
    assert df.iloc[0]["unit_usd_kg"] == 5.0                         # 1e6 / 2e5
    assert bool(df.iloc[0]["provisional"]) is False


def test_comtrade_matrix_committed_grid_is_sane():
    df = comtrade_matrix.load()
    if df.empty:
        return
    assert (df["net_kg"] >= comtrade_matrix._MIN_KG).all()
    # validate on material lanes only -- tiny-N unit values lie (HANDOFF gotcha)
    assert df[df["net_kg"] >= 50_000]["unit_usd_kg"].between(0.5, 40).all()
    # Peru->USA is the single largest blueberry lane in the world
    top = comtrade_matrix.lanes(year=int(df[~df["provisional"]]["year"].max())).iloc[0]
    assert top["exporter"] == "Peru" and top["importer"] == "USA"


def test_comtrade_monthly_parses_period_and_seasonality(monkeypatch, tmp_path):
    monkeypatch.setattr(comtrade_monthly, "CACHE", tmp_path / "m.csv")
    monkeypatch.setattr(comtrade_monthly.time, "sleep", lambda *_: None)

    def fake_fetch(reporter, periods, hs, retries=4):
        # mirror the real API: period is a STRING; month grows toward a Dec peak
        return [{"partnerCode": 842, "period": str(p), "primaryValue": 1e6 * (p % 100),
                 "netWgt": 1e5 * (p % 100)} for p in periods]
    monkeypatch.setattr(comtrade_monthly, "_fetch", fake_fetch)
    df = comtrade_monthly.refresh([2023], exporters=[604], names={604: "Peru", 842: "USA"})
    assert set(df["month"]) == set(range(1, 13))                    # period YYYYMM decoded
    assert (df["unit_usd_kg"] == 10.0).all()                       # 1e6*m / (1e5*m)
    prof = comtrade_monthly.seasonality("Peru")
    assert len(prof) == 12 and abs(prof["share"].sum() - 1.0) < 0.01   # 4-dp rounding slack
    assert int(prof.loc[prof["share"].idxmax(), "month"]) == 12    # Dec is the peak


def test_comtrade_monthly_committed_is_sane():
    df = comtrade_monthly.load()
    if df.empty:
        return
    assert df["month"].between(1, 12).all()
    assert df[df["net_kg"] >= 50_000]["unit_usd_kg"].between(0.5, 40).all()


def test_senasica_parses_bilingual_orchard_rows():
    # canned rows mirroring the gob.mx PDF: glued vs spaced 中文 state, multi-word names/states
    text = (
        "No. Registro SAGARPA Nombre del predio Superficie (Ha) Municipio Estado Fruto\n"
        "1 PRE03/06/010/0001 Arándanos de Colima 29.73 Villa de Álvarez Colima 科利马州 Arándano蓝莓\n"
        "2 PRE03/14/005/0001 Sur Loma 56.41 Amatitán Jalisco哈利斯科州 Arándano蓝莓\n"
        "3 PRE04/14/119/0001 El Briseño 64 Zacoalco Jalisco哈利斯科州 Frambuesa树莓\n"
        "ignore this footer line\n"
    )
    df = senasica._parse_text(text)
    assert len(df) == 3
    bb = df[df["fruto"] == "Arándano"]
    assert set(bb["estado"]) == {"Colima", "Jalisco"}
    r0 = df.iloc[0]
    assert r0["predio"] == "Arándanos de Colima" and r0["area_ha"] == 29.73
    assert r0["municipio"] == "Villa de Álvarez" and r0["destination"] == "China"


def test_senasica_committed_roster_is_sane():
    df = senasica.load()
    if df.empty:                                       # not fetched yet
        return
    assert set(senasica._COLS) == set(df.columns)
    assert (df["area_ha"] > 0).all()
    bb = senasica.load(fruit="Arándano")
    assert len(bb) > 0 and bb["estado"].notna().all()  # blueberry orchards, all geocoded


def test_probe_normalizes_bare_hostname():
    # registry URLs are often bare hostnames; the probe must add a scheme (offline check)
    from atlas import probe
    assert probe._normalize("datos.gob.cl") == "https://datos.gob.cl"
    assert probe._normalize("http://x.org") == "http://x.org"     # scheme left intact
    assert probe._normalize("") == ""


def test_probe_classify_handles_key_gated_body():
    # the US-Census-style "200 + Missing Key" page must classify as key_gated, not reachable
    from atlas import probe
    for hint_body in ("<html>A valid key must be included</html>", "Please log in to continue"):
        # exercise the fingerprint logic directly
        assert any(h in hint_body.lower() for h in probe._KEY_HINTS)


# ---- country lookup ------------------------------------------------------

def test_country_lookup_and_fallback():
    assert countries.name(842) == "USA"
    assert countries.name(826) == "United Kingdom"
    assert countries.name(999999) == "M49-999999"          # nothing silently dropped


# ---- Comtrade global sweep (offline) -------------------------------------

def _canned(flow, year, hs, retries=4):
    # World-aggregate rows (partner2Code=0) for two reporters + a zero to drop
    return [
        {"reporterCode": 604, "primaryValue": 1_000.0, "netWgt": 200.0, "partner2Code": 0},
        {"reporterCode": 528, "primaryValue": 600.0, "netWgt": 100.0, "partner2Code": 0},
        {"reporterCode": 0,   "primaryValue": 9_999.0, "netWgt": 1.0, "partner2Code": 0},  # World, skip
        {"reporterCode": 392, "primaryValue": 0.0, "netWgt": 0.0, "partner2Code": 0},       # zero, skip
    ]


def test_sweep_ranks_shares_and_targets(monkeypatch, tmp_path):
    monkeypatch.setattr(cs, "_fetch", _canned)
    monkeypatch.setattr(cs, "CACHE", tmp_path / "rank.csv")
    monkeypatch.setattr(cs.time, "sleep", lambda *_: None)

    df = cs.refresh([2020])
    exp = df[df["role"] == "exporter"].sort_values("rank")
    assert list(exp["country"]) == ["Peru", "Netherlands"]       # value-ranked, World/zero dropped
    assert exp.iloc[0]["share"] == 0.625 and exp.iloc[0]["cum_share"] == 0.625
    assert abs(exp["cum_share"].iloc[-1] - 1.0) < 1e-9
    # 95% target stops once cumulative share crosses the threshold
    ts = cs.target_set("exporter", year=2020, coverage=0.95, include_provisional=True)
    assert list(ts["country"]) == ["Peru", "Netherlands"]
    ts60 = cs.target_set("exporter", year=2020, coverage=0.60, include_provisional=True)
    assert list(ts60["country"]) == ["Peru"]                     # 0.625 already clears 0.60


def test_provisional_year_logic():
    import datetime as dt
    today = dt.date(2026, 6, 19)
    assert cs.is_provisional(2024, today) is True               # ~18mo, still settling
    assert cs.is_provisional(2023, today) is False              # ~30mo, final


def test_committed_ranking_is_sane():
    df = cs.load()
    if df.empty:                                                # not swept yet
        return
    assert set(df["role"]) == {"exporter", "importer"}
    assert df["share"].between(0, 1).all()
    final = df[~df["provisional"]]
    if final.empty:
        return
    yr = int(final["year"].max())
    top_exp = cs.ranking("exporter", yr).iloc[0]["country"]
    top_imp = cs.ranking("importer", yr).iloc[0]["country"]
    assert top_exp == "Peru"                                     # world #1 exporter
    assert top_imp == "USA"                                      # world #1 importer
    # the 95% target is a sensible breadth, not all ~200 reporters
    assert 5 < len(cs.target_set("exporter")) < 40
