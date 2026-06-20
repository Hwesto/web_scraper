"""Global trade reconciliation + backtest -- does the whole picture close?

The accounting identity: a country's EXPORTS must equal the WORLD'S IMPORTS from it.
This stitches the three layers into that identity and checks it closes:
  1. Comtrade both-flows bilateral -- the global backbone: exporter-reported exports to
     the world, and importer-reported world-imports-from-origin (the mirror).
  2. Eurostat monthly -- the EU importer slice, current to 2026 (fresher than Comtrade).
  3. Committee export totals (campaigns) -- the exporter side, current to 2025/26.

GLOBAL BACKTEST: for prior years, mirror_ratio = world-imports / exports should be ~1
(trade accounting closes, allowing for CIF/FOB + timing + non-reporters). Per origin we
also report the EU's accounted share (Eurostat) so the residual (US/China/Asia) is explicit.
Then the current (2025/26) row uses committee exports + Eurostat EU imports.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR, comtrade_matrix
from atlas import eurostat_monthly as em
from atlas import campaigns

CACHE = ATLAS_DIR / "global_reconcile.csv"
# major exporting origins: Comtrade display name -> ISO2 (Eurostat) -> campaigns name
ORIGINS = {
    "Peru": ("PE", "Peru"), "Chile": ("CL", "Chile"), "Morocco": ("MA", "Morocco"),
    "South Africa": ("ZA", "South Africa"), "Spain": ("ES", "Spain"),
    "Mexico": ("MX", "Mexico"), "Argentina": ("AR", "Argentina"),
}


def reconcile(years=(2022, 2023, 2024)) -> pd.DataFrame:
    bil = comtrade_matrix.load()
    exp = (bil[bil["flow"] == "exporter"].groupby(["year", "exporter"])["net_kg"].sum() / 1000)
    imp = (bil[bil["flow"] == "importer"].groupby(["year", "exporter"])["net_kg"].sum() / 1000)
    us = (bil[(bil["flow"] == "importer") & (bil["importer_code"] == 842)]    # US imports by origin
          .groupby(["year", "exporter"])["net_kg"].sum() / 1000)
    e = em.load()
    euimp = (e[(e["flow"] == "import") & (~e["intra_eu"])]
             .groupby(["year", "partner"])["net_kg"].sum() / 1000) if not e.empty else pd.Series(dtype=float)
    rows = []
    for name, (iso2, _camp) in ORIGINS.items():
        for y in years:
            x = exp.get((y, name)); w = imp.get((y, name))
            eu = euimp.get((y, iso2)); usv = us.get((y, name))
            if not x:
                continue
            acc = (eu or 0) + (usv or 0)
            rows.append({
                "origin": name, "year": y,
                "exports_t": round(x),
                "world_imports_t": round(w) if w else None,
                "mirror_ratio": round(w / x, 3) if w else None,
                "eu_imports_t": round(eu) if eu else None,
                "us_imports_t": round(usv) if usv else None,
                "eu_us_share": round(acc / x, 3) if acc else None,
                "residual_share": round(1 - acc / x, 3) if acc else None,
            })
    return pd.DataFrame(rows)


def current() -> pd.DataFrame:
    """Current row: committee export vs Eurostat EU imports (latest COMPLETE EU year, for a
    like-for-like share) -> the EU-accounted share, residual = US/China/Asia."""
    e = em.load()
    if e.empty:
        return pd.DataFrame()
    mc = e.groupby("year")["month"].nunique()
    full = mc[mc >= 12].index
    eu_year = int(full.max()) if len(full) else int(e["year"].max())
    euimp = (e[(e["flow"] == "import") & (~e["intra_eu"]) & (e["year"] == eu_year)]
             .groupby("partner")["net_kg"].sum() / 1000)                  # tonnes
    from atlas import berriesza, uscensus
    sa = berriesza.load()
    # US slice: live Census (if key set) else the latest complete Comtrade year
    usc = uscensus.load()
    if not usc.empty:
        usy = int(usc["year"].max())
        us_by = usc[usc["year"] == usy].groupby("partner")["net_kg"].sum() / 1000
        us_src = f"Census {usy}"
    else:
        b = comtrade_matrix.load()
        ub = b[(b["flow"] == "importer") & (b["importer_code"] == 842)]
        fin = ub[~ub["provisional"]] if "provisional" in ub.columns and (~ub["provisional"]).any() else ub
        usy = int(fin["year"].max())
        us_by = fin[fin["year"] == usy].groupby("exporter")["net_kg"].sum() / 1000
        us_src = f"Comtrade {usy}"
    rows = []
    for name, (iso2, camp) in ORIGINS.items():
        exp_t, season = None, ""
        if name == "South Africa" and len(sa):
            tot = sa[sa["region"] == "Total"]
            if len(tot):
                exp_t = float(tot.iloc[0]["total_t"]); season = str(tot.iloc[0]["season"])
        else:
            s = campaigns.latest(camp)
            for mt in ("export_total", "export_total_fresh"):
                r = s[s["metric"] == mt] if not s.empty else s
                if len(r):
                    exp_t = float(r.iloc[0]["value"]); season = str(r.iloc[0]["season"]); break
        eu = euimp.get(iso2); usv = us_by.get(name)
        acc = (eu or 0) + (usv or 0)
        rows.append({"origin": name,
                     "committee_export_kt": round(exp_t / 1000, 1) if exp_t else None,
                     "season": season,
                     f"eu_imports_{eu_year}_kt": round(eu / 1000, 1) if eu else None,
                     "us_imports_kt": round(usv / 1000, 1) if usv else None,
                     "eu_us_share": round(acc / exp_t, 3) if (acc and exp_t) else None,
                     "residual_share": round(1 - acc / exp_t, 3) if (acc and exp_t) else None})
    print(f"(US slice source: {us_src})")
    return pd.DataFrame(rows)


def refresh() -> pd.DataFrame:
    bt = reconcile()
    if not bt.empty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        bt.to_csv(CACHE, index=False)
    return bt


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame()
    return pd.read_csv(CACHE)


if __name__ == "__main__":
    bt = refresh()
    print("=== GLOBAL BACKTEST: world-imports vs exports (mirror should ~1) ===")
    print(bt.to_string(index=False))
    mr = bt["mirror_ratio"].dropna()
    if len(mr):
        print(f"\nmirror_ratio: median {mr.median():.2f}, mean {mr.mean():.2f} "
              f"(|1-ratio| median {((mr-1).abs()).median()*100:.0f}%)")
    print("\n=== CURRENT (2025/26): committee export + Eurostat EU imports + residual ===")
    print(current().to_string(index=False))
