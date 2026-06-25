"""Three price layers, increasing in value (all free):

1. import_unit_value()   -- HMRC import unit value GBP/kg by origin (value/volume).
                            Reconciled, by-origin, monthly, ~6wk lag. Context.
2. chile_fob_weekly()    -- weekly Chilean FOB USD/kg from the DUS feed (declared
                            export price), with the SAME ~2-week lead as volume.
                            This is landed COST, not the UK sell price.
3. (consumer retail scrape -- the demand-side UK price; forward-collection, see
                            data/retail_price.py. Sticky; weakly tracks supply.)
"""
from __future__ import annotations

import pandas as pd

from .config import REPO_ROOT, KG_PER_TONNE
from .store import vintage

FOB_CSV = REPO_ROOT / "data" / "weekly" / "chile_uk_blueberry_fob_weekly.csv"


def import_unit_value(origin: str | None = None, start: str = "2022-01-01") -> pd.Series | pd.DataFrame:
    """HMRC import unit value (GBP/kg), monthly. By origin, or one origin's series."""
    vol = vintage.latest("hmrc_blueberry_imports").copy()
    val = vintage.latest("hmrc_blueberry_import_value").copy()
    if vol.empty or val.empty:
        return pd.Series(dtype=float)
    for s in (vol, val):
        s["d"] = pd.to_datetime(s["ref_period"])
    m = vol.merge(val, on=["d", "key"], suffixes=("_t", "_gbp"))
    m = m[m["d"] >= start]
    m["gbp_per_kg"] = m["value_gbp"] / (m["value_t"] * KG_PER_TONNE)
    m = m[(m["value_t"] > 0)]
    if origin:
        return m[m["key"] == origin].set_index("d")["gbp_per_kg"].sort_index()
    return m.pivot_table(index="d", columns="key", values="gbp_per_kg")


def chile_fob_weekly(gbp: bool = False, usd_gbp: float | None = None) -> pd.Series:
    """Weekly Chilean FOB price (USD/kg, or GBP/kg if gbp=True at the real ECB rate).
    Indexed by ISO-week Monday. Empty until the cron has produced the file."""
    if not FOB_CSV.exists():
        return pd.Series(dtype=float, name="chile_fob")
    if usd_gbp is None:
        from deep.market import fx
        usd_gbp = fx.gbp_per_usd()
    df = pd.read_csv(FOB_CSV)
    df["d"] = df["iso_week"].map(
        lambda s: pd.Timestamp.fromisocalendar(int(s[:4]), int(s.split("-W")[1]), 1))
    s = df.set_index("d")["fob_usd_per_kg"].sort_index()
    s = s * usd_gbp if gbp else s
    s.name = "chile_fob_gbp" if gbp else "chile_fob_usd"
    return s
