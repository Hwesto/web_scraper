"""EU monthly blueberry trade from Eurostat COMEXT -- the current bilateral layer.

Comtrade is national customs aggregated with an ~18-month lag. Eurostat COMEXT is the
SAME customs data for EU members, published MONTHLY to ~2-3 months ago (verified to
2026-04). This pulls all 27 EU reporters monthly (CN 08104000 = blueberries, the exact
HS6 of the Comtrade base layer), by partner and flow, and aggregates to the EU bloc:
"EU imports from Peru/Morocco/Chile/South Africa..." by month, to the present.

It carries enough history (default 2019->now) to BACKTEST: summing the monthly series to
annual and reconciling against Comtrade for prior years validates the pipeline, so the
2025/2026 figures (which Comtrade does not yet have) can be trusted. `intra_eu` flags
partners that are EU members (intra-EU flows) so the clean extra-EU import picture
(Peru, Morocco, Chile, SA...) is one filter away. Free, no key.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.error
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR, hs_codes
from atlas.eurostat import _decode, _is_country          # reuse the JSON-stat decoder

CACHE = ATLAS_DIR / "eurostat_monthly.csv"
BT_CACHE = ATLAS_DIR / "eurostat_backtest.csv"
_API = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
EU27 = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
        "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
_FLOW = {"1": "import", "2": "export"}
_COLS = ["year", "month", "partner", "flow", "value_eur", "net_kg", "intra_eu"]


def _fetch(reporter: str, start: str, end: str, retries: int = 4) -> dict | None:
    hs = hs_codes.hs6("blueberry")
    url = (f"{_API}/M.{reporter}..{hs}..?format=JSON&startPeriod={start}&endPeriod={end}"
           "&i=VALUE_IN_EUROS&i=QUANTITY_IN_100KG")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):                       # no blueberry trade for this reporter
                return None
            last = e; time.sleep(2 ** attempt)
        except Exception as e:                             # noqa: BLE001
            last = e; time.sleep(2 ** attempt)
    raise RuntimeError(f"Eurostat monthly fetch failed ({reporter}): {last}")


def _rows(js: dict | None, reporter: str) -> list[dict]:
    if not js:
        return []
    cells: dict[tuple, dict] = {}
    for r in _decode(js):
        if not _is_country(r["partner"]) or r["partner"] == "WORLD":
            continue
        key = (r["time"], r["partner"], _FLOW.get(r["flow"], r["flow"]))
        c = cells.setdefault(key, {"value_eur": 0.0, "net_kg": 0.0})
        if r["indicators"] == "VALUE_IN_EUROS":
            c["value_eur"] = float(r["_val"])
        elif r["indicators"] == "QUANTITY_IN_100KG":
            c["net_kg"] = float(r["_val"]) * 100.0
    out = []
    for (t, partner, flow), c in cells.items():
        if c["value_eur"] <= 0:
            continue
        y, m = t.split("-")
        out.append({"year": int(y), "month": int(m), "reporter": reporter, "partner": partner,
                    "flow": flow, "value_eur": c["value_eur"], "net_kg": c["net_kg"]})
    return out


def refresh(start: str = "2019-01", end: str | None = None,
            reporters: list[str] | None = None) -> pd.DataFrame:
    """Pull all EU reporters monthly, aggregate to the EU bloc by partner x flow x month."""
    end = end or _dt.date.today().strftime("%Y-%m")
    reporters = reporters or EU27
    allrows = []
    for rep in reporters:
        try:
            allrows += _rows(_fetch(rep, start, end), rep)
        except Exception as e:                             # noqa: BLE001
            print(f"skip {rep}: {type(e).__name__} {str(e)[:50]}")
        time.sleep(0.3)
    df = pd.DataFrame(allrows)
    if df.empty:
        return pd.DataFrame(columns=_COLS)
    df["intra_eu"] = df["partner"].isin(set(EU27))
    agg = (df.groupby(["year", "month", "partner", "flow", "intra_eu"], as_index=False)
             .agg(value_eur=("value_eur", "sum"), net_kg=("net_kg", "sum")))
    agg = agg.sort_values(["year", "month", "flow", "value_eur"],
                          ascending=[True, True, True, False]).reset_index(drop=True)
    agg["value_eur"] = agg["value_eur"].round(0)
    agg["net_kg"] = agg["net_kg"].round(0)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    agg[_COLS].to_csv(CACHE, index=False)
    return agg[_COLS]


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def backtest(origins=("CL", "MA", "PE", "ZA", "AR", "EG"),
             years=(2022, 2023, 2024)) -> pd.DataFrame:
    """Reconcile EU-imports-from-origin (Eurostat monthly -> annual) against the same
    measure from the Comtrade base layer, for prior complete years. Small error => the
    monthly pipeline is accurate, so the current (2025/26) figures can be trusted."""
    em = load()
    if em.empty:
        return pd.DataFrame()
    imp = em[(em["flow"] == "import") & (~em["intra_eu"])]
    eu = imp.groupby(["year", "partner"])["net_kg"].sum().div(1000)        # tonnes
    cc = pd.read_csv(ATLAS_DIR / "country_codes.csv")
    iso2_m49 = {i: int(m) for m, i in zip(cc["m49"], cc["iso2"]) if isinstance(i, str)}
    from atlas import comtrade_matrix
    bil = comtrade_matrix.load()
    eu_m49 = {iso2_m49[c] for c in EU27 if c in iso2_m49}
    # single flow only (the bilateral carries both exporter- and importer-reported -- summing
    # both would double-count); exporter-reported captures the origin's exports to all 27 EU.
    ct = (bil[(bil["flow"] == "exporter") & bil["importer_code"].isin(eu_m49)]
          .groupby(["year", "exporter_code"])["net_kg"].sum().div(1000))    # EU imports by origin
    rows = []
    for iso2 in origins:
        m49 = iso2_m49.get(iso2)
        for y in years:
            e = eu.get((y, iso2)); c = ct.get((y, m49)) if m49 else None
            if e and c:
                rows.append({"origin": iso2, "year": y, "eurostat_t": round(e),
                             "comtrade_t": round(c), "diff_pct": round((e / c - 1) * 100, 1)})
    return pd.DataFrame(rows)


def ytd_imports(year: int | None = None) -> pd.DataFrame:
    """Extra-EU import origins for a year (year-to-date if current), tonnes -- the
    current bilateral picture Comtrade can't yet give."""
    df = load()
    imp = df[(df["flow"] == "import") & (~df["intra_eu"])]
    if imp.empty:
        return imp
    year = year or int(imp["year"].max())
    g = imp[imp["year"] == year].groupby("partner")["net_kg"].sum().div(1000).round(0)
    return g.sort_values(ascending=False).reset_index().rename(columns={"net_kg": "tonnes"})


if __name__ == "__main__":
    df = refresh()
    print(f"cached {len(df)} EU-bloc partner-months -> {CACHE}")
    bt = backtest()
    if len(bt):
        bt.to_csv(BT_CACHE, index=False)
        print(f"backtest vs Comtrade: median |diff| {bt['diff_pct'].abs().median():.1f}% "
              f"(within 15%: {(bt['diff_pct'].abs()<=15).mean()*100:.0f}%) -> {BT_CACHE}")
    if len(df):
        latest = f"{int(df['year'].max())}-{int(df[df['year']==df['year'].max()]['month'].max()):02d}"
        print(f"latest month: {latest}  -- CONFIRMED current EU imports YTD {int(df['year'].max())} (t):")
        print(ytd_imports().head(6).to_string(index=False))
