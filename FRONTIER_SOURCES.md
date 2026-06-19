# Current-season data frontier — what's available, per country

The layer UN Comtrade / FAOSTAT can't reach (they lag ~18 months): grower-committee and
official current-season export/production data. Mapped via a 2026-06 sweep. The structured
version lives in the registry (`data_point = "current-season export tracker"`); the
confirmed numbers are wired in `atlas/campaigns.py` → `data/atlas/campaigns.csv`.

**One-line finding:** the **USA is the only market with a true free current-season API**
(USDA-AMS Market News). Everyone else is a committee **PDF** or a **press** snapshot —
Peru's ProArándanos pattern is the norm. None of the free committee feeds name exporter
companies (that's paid: Agronometrics / Agrodata / Tridge).

## The map

| Country | Best current-season source | Format | Latest confirmed | Verdict |
|---|---|---|---|---|
| **Peru** | ProArándanos (via press) | dashboard → press | 2025/26 ≈ **383 kt** (+20%), peak wk40 21 kt | SNAPSHOT ✅ wired |
| **Chile** | Comité de Arándanos / Frutas de Chile (iQonsulting) | weekly **PDF**, predictable URL | 2025/26 fresh ≈ **92 kt** (+2%); frozen 72 kt | MEDIUM ✅ wired |
| **South Africa** | Berries ZA (ex-SABPA) export reports | weekly **PDF** `/download/<id>/` | 2025/26 ≈ **25.8 kt** to wk4 (+14%) | MEDIUM ✅ wired |
| **Argentina** | ABC — Argentine Blueberry Committee | weekly **PDF** | 2025 ≈ **6 kt** (US 33% / NL 25%) | MEDIUM ✅ wired |
| **Mexico** | Aneberries | weekly, **member-gated → press** | 2023/24 ≈ **79 kt** | SNAPSHOT ✅ wired |
| **Spain** | FEPEX (Aduanas) + Freshuelva + Junta de Andalucía Observatorio | **Excel** + weekly **PDF** | 2025 exports **100.2 kt**; Huelva 63 kt | EASY/MEDIUM ✅ wired |
| **Morocco** | APEFEL / EastFruit (Foodex BI is gated) | **press** | 2024/25 ≈ **82 kt** (+20%) | SNAPSHOT ✅ wired |
| **USA** | **USDA-AMS Market News** — WA_FV408 (slug 3251) + FOB reports | weekly **JSON API** (+ keyless TXT mirror) | live to 2026-06 (FOB confirmed) | **EASY** ⬜ wire next |
| **Canada** | StatCan tbl 32-10-0364-01 (WDS API) | annual **CSV/JSON API** | 2024 = 165.6 kt | EASY but annual ⬜ |
| **Poland** | EastFruit / GUS BDL | press / weak API | 2024 prod 62 kt, exp 26 kt | SNAPSHOT |
| **Portugal** | — (no committee feed; only lagging INE/GPP) | — | 2023 area ≈ 21 kt | NONE |
| **Netherlands** | — (re-export hub; no production feed) | CBS/Eurostat for flows | "Cijfers 2021" factsheet | NONE (use Eurostat) |
| **China** | — (press only; Yunnan output) | press | 2025 output ≈ 810 kt | NONE/SNAPSHOT |

## Wireable tiers
- **EASY (clean feed/API):** USDA-AMS Market News (US weekly movement + FOB — the prize, free key or keyless `ams.usda.gov/mnreports/wa_fv408.txt`); FEPEX Excel (Spain); StatCan WDS (Canada, annual); Eurostat COMEXT CN 08104000 (all EU, blueberry-pure, ~2–3 mo lag — already wired).
- **MEDIUM (parse PDFs):** Chile (Comité), South Africa (Berries ZA), Argentina (ABC), Spain (Andalucía Observatorio). Clean predictable public PDF URLs.
- **SNAPSHOT (hand-curate press):** Peru (ProArándanos), Mexico (Aneberries), Morocco (APEFEL/EastFruit), Poland (EastFruit).
- **NONE:** Portugal, Netherlands (production), China — no free current-season blueberry feed.

## Paid-only (what they'd add)
- **Agronometrics** — weekly exporter-**named** customs data (ex-SUNAT: Camposol, Agrovisión…), "Exports by Company"; repackages USDA + customs. ~US$5k/yr (self-reported).
- **iQonsulting** — Intl Blueberry Yearbook + weekly commercial report (arrivals/prices).
- **Agrodata Perú / Tridge** — ex-customs / bills-of-lading, supplier names + prices.
- **Mintec/Expana, Comtrade Premium** — benchmark price series / bulk HS (no company names).

## Next rungs (genuine wins still on the table)
1. **USDA-AMS WA_FV408** — the only true weekly API; covers Peru/Chile/Mexico *arrivals into the US* as a free cross-check on the committee numbers. Keyless TXT mirror is reachable. **Highest-value next wire.**
2. **Chile / South Africa / Argentina weekly PDFs** — automate the season snapshots now hand-curated in `campaigns.csv`.
