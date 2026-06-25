"""Who can actually chase the Asia premium? -- phyto access x netback.

The netback layer says Asia pays the most per kg; this says *which named Chilean
producers in our flow are cleared to ship there*. China access is gated: GACC only
admits fruit from SAG-registered predios (the ~71-orchard list). We match our named
producers to that roster (nowcast.farm.sag_china) and weight each by the per-kg
premium Asia nets over the US bulk lane -- so a grower can see the prize and whether
the door is open.

The roster itself (SAG "Listado de predios de arandanos a China", a Power BI /
Excel publish) is fetched by the cron into data/market/sag_china_orchards.csv; this
module degrades gracefully when it is not yet present.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from deep.config import DATA_DIR
from deep.farm import sag_china
from deep.market import netback

ROSTER = DATA_DIR / "market" / "sag_china_orchards.csv"
_ASIA = {"South Korea", "China", "Japan", "Taiwan", "Hong Kong", "Singapore",
         "Other Asia, nes"}


def asia_premium_usd_kg(year: int | None = None) -> float:
    """Volume-weighted Asian netback minus the US netback, per kg."""
    t = netback.netback_table(year)
    if t.empty:
        return 0.0
    asia = t[t["destination"].isin(_ASIA)]
    us = t[t["destination"] == "United States"]["netback_usd_kg"]
    if asia.empty or us.empty:
        return 0.0
    w = (asia["netback_usd_kg"] * asia["net_kg"]).sum() / asia["net_kg"].sum()
    return float(w - us.iloc[0])


def ranked(roster_csv: str | Path = ROSTER) -> pd.DataFrame:
    """Our named producers, flagged for China access and ranked by the prize.

    prize_usd = the Asia-over-US premium applied to the producer's volume -- a proxy
    for how much an approved grower stands to gain by steering fruit east.
    Empty frame if the roster has not been fetched yet.
    """
    roster_csv = Path(roster_csv)
    if not roster_csv.exists():
        return pd.DataFrame()
    cr = sag_china.crossref(roster_csv)
    res = cr["table"].copy()
    prem = asia_premium_usd_kg()
    res["asia_premium_usd_kg"] = prem
    res["prize_usd"] = res["china_approved"] * prem * res["net_kg"]
    return res.sort_values(["china_approved", "net_kg"], ascending=False).reset_index(drop=True)


def summary(roster_csv: str | Path = ROSTER) -> dict:
    r = ranked(roster_csv)
    if r.empty:
        return {"available": False, "asia_premium_usd_kg": round(asia_premium_usd_kg(), 2)}
    approved = r[r["china_approved"]]
    return {
        "available": True,
        "asia_premium_usd_kg": round(asia_premium_usd_kg(), 2),
        "n_producers": len(r),
        "n_china_approved": int(r["china_approved"].sum()),
        "approved_kg_share_%": round(100 * approved["net_kg"].sum() / r["net_kg"].sum(), 1),
        "top_approved": approved.head(10),
    }


if __name__ == "__main__":
    s = summary()
    if not s["available"]:
        print(f"roster not fetched yet (data/market/sag_china_orchards.csv). "
              f"Asia premium over US: ${s['asia_premium_usd_kg']}/kg")
    else:
        print(f"Asia premium ${s['asia_premium_usd_kg']}/kg | "
              f"{s['n_china_approved']}/{s['n_producers']} producers China-approved "
              f"({s['approved_kg_share_%']}% of our UK volume)")
