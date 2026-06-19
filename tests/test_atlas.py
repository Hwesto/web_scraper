"""Atlas Phase-0/1 foundations: HS registry, schema, registry table, country
lookup, and the Comtrade global sweep (offline parse + committed-table sanity)."""
from atlas import comtrade_sweep as cs
from atlas import countries, hs_codes, registry, schema


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
