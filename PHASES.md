# PHASES — the road to "absolute maximum" on 1–3 (then 4)

Decision (this session): **do not start Phase 4 (other fruits) until Phases 1, 2 and 3 are
reinforced to their maximum.** Phase 4 is only an HS-code swap; it proves the machine
generalises *only once the machine is actually complete*. So: max the foundation, then flip.

Status keys: `[x]` done · `[~]` partial · `[ ]` todo. Checked items link to the module.

---

## Phase 1 — the global base layer (Comtrade + HS registry) → MAXIMUM
The free global flow+price spine. "Maximum" = the entire matrix, full history, both
directions, every quality flag, and a complete HS join key.

- [x] Exporter & importer **ranking** (annual, target set) — `atlas/comtrade_sweep.py`
- [x] **Bilateral grid** annual (exporter target set) — `atlas/comtrade_matrix.py`
- [x] **Monthly** bilateral (seasonality, baseline) — `atlas/comtrade_monthly.py`
- [x] HS6 + partial national splits — `atlas/hs_codes.py`
- [x] **Full history 2012→present** on ranking + bilateral (code; runner populates);
      monthly on a rolling 6-yr window (call-cost bound) — `START_YEAR=2012`
- [x] Bilateral grid covers **both flows** — exporter-reported (X) + importer-reported (M),
      oriented exporter→importer with a `flow` tag; `comtrade_matrix.mirror_check()`
- [x] **Per-year coverage/quality table** — `comtrade_sweep.coverage_by_year()` (reporters
      filed, total value, provisional flag)
- [x] HS registry **completed**: fresh 081040 (+UK/EU/US splits), **frozen 0811.90**,
      **dried 0813.40**; other-fruit HS6 seeded (note: frozen/dried aren't blueberry-
      specific at HS6 — only national CN8 splits them, captured where commercial)
- [x] **Reconciliation** — `mirror_check()` (exporter- vs importer-reported, ratio≈1)
      is the World-total/mirror cross-check

> **Phase 1 = COMPLETE.** Global flow+price (annual full-history + monthly seasonality,
> both flows, coverage lens) + complete HS join key.

## Phase 2 — the overlay catalogue (breadth) → MAXIMUM
Every country in the trade that matters, every overlay category, every source probed.

- [x] Top 8 exporters catalogued — registry Phase 2
- [x] 12 importer/hub countries catalogued — registry Phase 2b
- [~] **Every country in the 95% set, both roles** (gaps: some importers — SG/DK/UAE/IE/JP rows)
- [ ] **All 5 overlay categories filled** per country (customs · shipment/BoL · phyto ·
      area census · forecast) — no blank category without a "none found" verdict
- [ ] **Every source URL probed**, verified_date or documented block (runner re-probe covers
      the sandbox-blocked ones — confirm all resolve or are flagged)
- [ ] Push coverage from 95% → **99% of trade** (long tail of small origins/markets)
- [ ] Catalogue the **paid-broker layer** explicitly per country (BoL providers, etc.)

## Phase 3 — depth (wire the free overlays into real data) → MAXIMUM
Every free, parseable overlay identified in Phase 2 becomes a fetcher + cache + test +
wired registry row. "Maximum" = nothing free and parseable left merely catalogued.

- [x] Eurostat COMEXT (EU trade) — `atlas/eurostat.py`
- [x] Comtrade bilateral + monthly grids — `atlas/comtrade_matrix.py` / `comtrade_monthly.py`
- [x] Mexico SENASICA orchards (China list) — `atlas/senasica.py`
- [ ] SENASICA **Korea + EU** berry lists (same parser, more lanes)
- [ ] **GACC CIFER** registered overseas producers (named entities, China imports)
- [ ] Morocco **ONSSA** approved packing stations (PDF)
- [ ] National customs with clean access: **US Census**, **Canada ISED/StatCan**, **Japan
      e-Stat/Customs**, **Korea KITA**, **Switzerland Swiss-Impex**, **Serbia SORS**,
      **Mexico INEGI/Banxico**, **South Africa SARS**
- [x] **Global area/production/yield base layer — FAOSTAT** (`atlas/faostat.py`), all
      countries, one keyless bulk. National censuses below are now finer *overlays*.
- [ ] National **area/production overlays** (variety/planting-year/sub-national): USDA
      **NASS QuickStats** (US), Spain **ESYRCE**, Mexico SIAP, Canada StatCan, others
- [ ] **EUROPHYT/AGRINFO** plant-health interceptions
- [ ] USDA-FAS **GAIN** multi-country forecasts (PDF; runner-only, fragile — last)

---

## Execution order
Foundation-up: **finish Phase 1 → fill Phase 2 → wire Phase 3**, then Phase 4 (HS swap).
Heavy network pulls (full history, full monthly) run on the **clean-egress runner**
(`atlas-refresh.yml`); the sandbox commits parseable baselines + the code.
Every wiring: verify reachable/parseable first (standing rule), add a test, flip the
registry `wired` flag, keep the suite green.
