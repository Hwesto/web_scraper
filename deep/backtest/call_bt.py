"""Back-test 'this week's call' -- both halves, honestly and separately.

The panel makes two claims per in-season month:
  SUPPLY: nowcast says arrivals are SHORT/LONG vs the seasonal norm.
  PRICE : therefore UK price will move UP/DOWN over the next ~month (lock/move).

We score each on a walk-forward, decision-time-only:
  (1) supply directional skill  -- does the nowcast call the sign of the realised
      supply anomaly?  (re-confirms the validated nowcast)
  (2) price-call skill -- does the lean (LONG supply -> price down) actually
      predict the realised forward price move?  (the inference layer; expected weak)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .within_month import _hmrc_chile, origin_implied_monthly
from ..benchmarks import seasonal_naive
from ..store import vintage

_ANOM = 0.12
_INSEASON_T = 100.0


def _ons_price() -> pd.Series:
    f = vintage.latest("ons_blueberry_retail_price").copy()
    f["d"] = pd.to_datetime(f["ref_period"])
    return f.set_index("d")["value"].sort_index().resample("MS").mean()


def run(min_train: int = 24, transit_weeks: int = 2, horizon_m: int = 1) -> dict:
    hmrc = _hmrc_chile()
    implied = origin_implied_monthly(transit_weeks)
    price = _ons_price()
    months = pd.date_range(hmrc.index.min(), hmrc.index.max(), freq="MS")
    hmrc = hmrc.reindex(months, fill_value=0.0)
    implied = implied.reindex(months, fill_value=0.0)

    rows = []
    for i in range(min_train, len(months)):
        M = months[i]
        train = hmrc.iloc[:i]
        ov = pd.concat([train.rename("h"), implied.iloc[:i].rename("e")], axis=1).dropna()
        ov = ov[ov["e"] > 0]
        scale = float(ov["h"].sum() / ov["e"].sum()) if len(ov) and ov["e"].sum() else 1.0
        norm = seasonal_naive(train, 1)
        if not norm or norm < _INSEASON_T:
            continue                                   # off-season: no call
        nowcast = scale * float(implied.iloc[i])
        realized = float(hmrc.iloc[i])
        supply_anom = (nowcast - norm) / norm
        realized_anom = (realized - norm) / norm
        # forward price move over the horizon
        p0 = price.get(M, np.nan)
        pH = price.get(M + pd.DateOffset(months=horizon_m), np.nan)
        fwd = (pH / p0 - 1) if (p0 == p0 and pH == pH and p0) else np.nan
        rows.append({"month": f"{M.year}-{M.month:02d}", "supply_anom": supply_anom,
                     "realized_anom": realized_anom, "fwd_price_chg": fwd})
    df = pd.DataFrame(rows)

    # (1) supply directional skill (sign of nowcast anomaly vs realised)
    s = df.dropna(subset=["supply_anom", "realized_anom"])
    sv = (np.sign(s["supply_anom"]) == np.sign(s["realized_anom"]))
    supply_dir = round(100 * sv.mean(), 1) if len(s) else float("nan")

    # (2) price-call skill: lean = -sign(supply_anom); hit if forward price agrees
    called = df[(df["supply_anom"].abs() > _ANOM) & df["fwd_price_chg"].notna()].copy()
    called["lean"] = -np.sign(called["supply_anom"])              # LONG supply -> price down
    price_hit = (np.sign(called["fwd_price_chg"]) == called["lean"])
    price_dir = round(100 * price_hit.mean(), 1) if len(called) else float("nan")
    both = df.dropna(subset=["supply_anom", "fwd_price_chg"])
    corr = round(float(both["supply_anom"].corr(both["fwd_price_chg"])), 2) if len(both) > 3 else float("nan")

    return {"n_calls": len(df), "supply_dir_skill_%": supply_dir, "n_supply": len(s),
            "price_call_dir_skill_%": price_dir, "n_price_calls": len(called),
            "corr_supply_anom_vs_fwd_price": corr, "table": df}


if __name__ == "__main__":
    r = run()
    print(f"in-season calls: {r['n_calls']}")
    print(f"SUPPLY call directional skill: {r['supply_dir_skill_%']}%  (n={r['n_supply']}, vs 50% coin-flip)")
    print(f"PRICE call directional skill:  {r['price_call_dir_skill_%']}%  (n={r['n_price_calls']} non-normal calls)")
    print(f"corr(supply anomaly, forward price move): {r['corr_supply_anom_vs_fwd_price']}  (negative = thesis holds)")
