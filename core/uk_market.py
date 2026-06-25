"""View 1 — who supplies Britain, when, at what landed price, + variety.

Players ranked by share of UK imports (HMRC, last 12 months), each with its season
peak month and the price it's brought in at (CIF £/kg — the declared landed value;
a solid proxy, though much soft fruit is consignment-settled). Variety is filled for
Chile (DUS cultivar mix) and blank elsewhere — the honest data asymmetry. Plus the
UK's own British-season production and self-sufficiency.
"""
from __future__ import annotations

import pandas as pd

from nowcast import price
from nowcast.config import REPO_ROOT
from nowcast.store import vintage
from core import uk_production

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _chile_varieties(n: int = 3) -> str:
    f = REPO_ROOT / "data" / "weekly" / "chile_uk_blueberry_by_producer.csv"
    if not f.exists():
        return ""
    p = pd.read_csv(f)
    cv = (p.groupby("top_cultivar")["net_kg"].sum().sort_values(ascending=False))
    cv = cv[cv.index.astype(str).str.strip() != ""]
    return ", ".join(c.title() for c in cv.head(n).index)


def into_uk(min_share: float = 0.5) -> pd.DataFrame:
    """Per-origin: share %, peak month, CIF £/kg brought in, variety (Chile)."""
    v = vintage.latest("hmrc_blueberry_imports").copy()
    v["d"] = pd.to_datetime(v["ref_period"])
    last12 = v[v["d"] >= v["d"].max() - pd.DateOffset(months=11)]
    share = last12.groupby("key")["value"].sum() / last12["value"].sum() * 100
    v3 = v[v["d"] >= v["d"].max() - pd.DateOffset(months=35)].copy()
    v3["m"] = v3["d"].dt.month
    pk = v3.groupby(["key", "m"])["value"].sum().reset_index()
    peakmo = pk.loc[pk.groupby("key")["value"].idxmax()].set_index("key")["m"]
    cif = price.import_unit_value()
    cif12 = cif[cif.index >= cif.index.max() - pd.DateOffset(months=11)].mean()
    df = pd.DataFrame({"share_pct": share.round(1),
                       "peak_month": peakmo.map(lambda m: _MONTHS[int(m) - 1]),
                       "cif_gbp_kg": cif12.round(2)})
    df = df[df["share_pct"] >= min_share].sort_values("share_pct", ascending=False)
    df["variety"] = ""
    if "Chile" in df.index:
        df.loc["Chile", "variety"] = _chile_varieties()
    df.index.name = "origin"
    return df.reset_index()


def uk_supply() -> dict:
    """Imports total, UK production, and self-sufficiency for the latest year."""
    v = vintage.latest("hmrc_blueberry_imports").copy()
    v["d"] = pd.to_datetime(v["ref_period"])
    imp_kt = v[v["d"] >= v["d"].max() - pd.DateOffset(months=11)]["value"].sum() / 1000
    prod = uk_production.load()
    prod_kt = float(prod["production_kt"].iloc[-1]) if not prod.empty else float("nan")
    sd = prod_kt / (imp_kt + prod_kt) * 100 if imp_kt and prod_kt == prod_kt else float("nan")
    return {"imports_kt": round(imp_kt, 1), "uk_production_kt": prod_kt,
            "self_sufficiency_pct": round(sd, 1) if sd == sd else None}


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    print("VIEW 1 — into the UK (last 12 months):")
    print(into_uk().to_string(index=False))
    print("\nUK supply:", uk_supply())
