"""Forecast-vs-actual divergence tracker -- where reality broke from the projections.

The atlas's highest-value lens: it holds both the official PROJECTIONS (USDA-FAS GAIN
forecasts, committee season growth) and the fresh ACTUALS (Eurostat to 2026, the China
snapshot, committee totals). This compares them per origin and flags the divergences --
the things that changed since the forecast.

It is what caught, automatically, the 2025/26 stories the static forecasts missed:
Peru beating its GAIN export forecast, the Chancay-driven Peru->China surge, the Chile<->Peru
swap in Europe, and Morocco's momentum reversal. Output -> data/atlas/divergence.csv.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR
from atlas import usda_gain, campaigns, china
from atlas import eurostat_monthly as em

CACHE = ATLAS_DIR / "divergence.csv"
_ISO = {"Peru": "PE", "Chile": "CL", "Morocco": "MA", "South Africa": "ZA",
        "Argentina": "AR", "Spain": "ES", "Mexico": "MX"}


def _eu_yoy(iso, y0, y1):
    e = em.load()
    if e.empty:
        return None
    imp = e[(e["flow"] == "import") & (~e["intra_eu"]) & (e["partner"] == iso)]
    a = imp[imp["year"] == y0]["net_kg"].sum() / 1000
    b = imp[imp["year"] == y1]["net_kg"].sum() / 1000
    return (b / a - 1) * 100 if a else None


def _eu_ytd_yoy(iso, y1=2026, y0=2025, mmax=4):
    e = em.load()
    if e.empty:
        return None
    imp = e[(e["flow"] == "import") & (~e["intra_eu"]) & (e["partner"] == iso) & (e["month"] <= mmax)]
    a = imp[imp["year"] == y0]["net_kg"].sum() / 1000
    b = imp[imp["year"] == y1]["net_kg"].sum() / 1000
    return (b / a - 1) * 100 if a else None


def _flag(proj, actual, *, reversal_if_sign=True):
    """Classify a projection vs actual (both % growth, unless absolute)."""
    if proj is None or actual is None:
        return "—"
    if reversal_if_sign and proj > 0 and actual < -2:
        return "REVERSAL"
    d = actual - proj
    if d > 5:
        return "BEAT"
    if d < -5:
        return "MISS"
    return "on-track"


def build() -> pd.DataFrame:
    rows = []
    fc = usda_gain.load()
    camp = campaigns.load()

    # 1. GAIN export forecast vs committee actual (absolute)
    for country, actual_kt in [("Peru", _campaign_total("Peru")), ("Mexico", _campaign_total("Mexico"))]:
        gf = fc[(fc["country"] == country) & (fc["metric"] == "exports")]
        if len(gf) and actual_kt:
            proj = gf.iloc[0]["value_mt"] / 1000
            gap = (actual_kt / proj - 1) * 100
            rows.append({"entity": country, "dimension": "exports vs USDA-GAIN forecast",
                         "projection": f"{proj:.0f}kt", "actual": f"{actual_kt:.0f}kt",
                         "gap": f"{gap:+.0f}%", "flag": "BEAT" if gap > 5 else ("MISS" if gap < -5 else "on-track"),
                         "note": "blew past the official forecast" if gap > 5 else "",
                         "sources": "USDA-GAIN / committee"})

    # 2. committee projected season growth vs actual EU-import momentum
    notes = {"Chile": "far above the committee's flat call -- pivoting to the EU",
             "Peru": "but 2026 YTD only {ytd:+.0f}% -- diverting to China (Chancay)",
             "Morocco": "momentum reversed in early 2026",
             "South Africa": "quiet outperformer"}
    for country, iso in _ISO.items():
        pr = camp[(camp["country"] == country) & (camp["metric"] == "yoy_growth")]
        if not len(pr):
            continue
        proj = float(pr.iloc[0]["value"])
        act = _eu_yoy(iso, 2024, 2025)
        ytd = _eu_ytd_yoy(iso)
        if act is None:
            continue
        flag = _flag(proj, ytd if (ytd is not None and ytd < -2) else act)
        note = notes.get(country, "").format(ytd=ytd) if ytd is not None else notes.get(country, "")
        rows.append({"entity": country, "dimension": "EU-import growth vs committee projection",
                     "projection": f"+{proj:.0f}%", "actual": f"{act:+.0f}% (2025), {ytd:+.0f}% (26-YTD)" if ytd is not None else f"{act:+.0f}%",
                     "gap": f"{act-proj:+.0f}pp", "flag": flag, "note": note, "sources": "committee / Eurostat"})

    # 3. the unforecast surprise: Peru -> China (Chancay)
    if china.latest("import", "Peru"):  # value $266M row exists
        rows.append({"entity": "Peru->China", "dimension": "import value (unforecast)",
                     "projection": "—", "actual": "+153% ($105M->$266M)", "gap": "+153%",
                     "flag": "SURPRISE", "note": "Chancay direct route; not in any forecast",
                     "sources": "GACC via Produce Report"})
    df = pd.DataFrame(rows)
    if not df.empty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE, index=False)
    return df


def _campaign_total(country):
    c = campaigns.latest(country)
    for mt in ("export_total", "export_total_fresh"):
        r = c[c["metric"] == mt] if not c.empty else c
        if len(r):
            return float(r.iloc[0]["value"]) / 1000
    return None


def load() -> pd.DataFrame:
    return pd.read_csv(CACHE) if CACHE.exists() else pd.DataFrame()


if __name__ == "__main__":
    df = build()
    print("FORECAST vs ACTUAL -- where reality broke from the projections:")
    print(df.to_string(index=False))
