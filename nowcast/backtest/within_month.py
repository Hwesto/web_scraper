"""Within-month nowcast test: does WEEKLY origin export beat seasonal-naive?

The monthly origin series failed the turning-point bar (backtest/lead.py) because
the 3-5 week transit lead collapses at monthly resolution. This re-runs the
identical bar with the WEEKLY DUS exports: shift each export week by the deep-sea
transit time to the UK-arrival week, aggregate to the arrival month, scale
(train-calibrated, absorbing the ~12% transhipment gap), and predict the HMRC
Chile import print for month M -- which physically departed weeks earlier, so it
is knowable before HMRC prints (~6 weeks after month end).

Target = HMRC import (independent of the DUS-sourced predictor). Scored vs
seasonal-naive / persistence on the anomaly (deviation from seasonal-naive),
walk-forward, in-season and all-months. A synthetic guard (tests/) proves the
test can detect a real lead, so a null is genuine.

Honest caveat: this asserts the relevant export months' DUS files are published
before HMRC's month-M print. The transit shift means month M's arrivals come
mostly from month M-1 departures, whose monthly DUS file lands earlier -- so the
assumption is reasonable, but it is an assumption.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..benchmarks import persistence, seasonal_naive
from ..store import vintage
from ..volume.data.chile_weekly import load_weekly_exports
from . import metrics


def _hmrc_chile() -> pd.Series:
    f = vintage.latest("hmrc_blueberry_imports")
    f = f[f["key"] == "Chile"].copy()
    f["d"] = pd.to_datetime(f["ref_period"])
    return f.set_index("d")["value"].sort_index()


def origin_implied_monthly(transit_weeks: int = 4) -> pd.Series:
    """Weekly exports shifted by transit -> summed into UK-arrival months (t)."""
    exp = load_weekly_exports(fill_zeros=True)
    if exp.empty:
        return exp
    arrivals = exp.copy()
    arrivals.index = arrivals.index + pd.Timedelta(weeks=transit_weeks)
    months = arrivals.index.to_series().apply(
        lambda d: (d + pd.Timedelta(days=3)).replace(day=1))   # week's Thursday month
    return arrivals.groupby(months).sum()


def run(transit_weeks: int = 4, min_train: int = 24,
        hmrc: pd.Series | None = None, implied: pd.Series | None = None) -> dict:
    hmrc = _hmrc_chile() if hmrc is None else hmrc
    implied = origin_implied_monthly(transit_weeks) if implied is None else implied
    months = pd.date_range(min(hmrc.index.min(), implied.index.min()),
                           hmrc.index.max(), freq="MS")
    hmrc = hmrc.reindex(months, fill_value=0.0)
    implied = implied.reindex(months, fill_value=0.0)

    rows = []
    for i in range(min_train, len(months)):
        M = months[i]
        train_h = hmrc.iloc[:i]
        # scale calibrated on train overlap only (absorbs the export>import gap)
        tr = pd.concat([train_h.rename("h"), implied.iloc[:i].rename("e")], axis=1)
        tr = tr[tr["e"] > 0]
        scale = float(tr["h"].sum() / tr["e"].sum()) if tr["e"].sum() > 0 else 1.0
        norm = seasonal_naive(train_h, 1)
        rows.append({"month": f"{M.year}-{M.month:02d}", "actual": float(hmrc.iloc[i]),
                     "seasonal_norm": norm, "seasonal_naive": norm,
                     "persistence": persistence(train_h, 1),
                     "origin_nowcast": scale * float(implied.iloc[i])})
    df = pd.DataFrame(rows)

    def score(sub, label):
        a, norm = sub["actual"].values, sub["seasonal_norm"].values
        base = metrics.accuracy(a, sub["seasonal_naive"].values)["mae"]
        out = {"label": label, "n": len(sub)}
        for m in ["seasonal_naive", "persistence", "origin_nowcast"]:
            acc = metrics.accuracy(a, sub[m].values)
            out[m] = {"mae": round(acc["mae"], 0),
                      "dir_skill_%": round(metrics.directional_skill(a, sub[m].values, norm), 1),
                      "skill_vs_snaive_%": round(metrics.skill_vs(acc["mae"], base), 1)}
        return out

    inseason = df[df["seasonal_norm"] >= 100.0]
    return {"transit_weeks": transit_weeks, "all": score(df, "all months"),
            "in_season": score(inseason, "in-season only"), "table": df}


if __name__ == "__main__":
    for tw in (3, 4, 5):
        r = run(transit_weeks=tw)
        print(f"\n=== transit={tw}w | in-season (n={r['in_season']['n']}) ===")
        for m in ["seasonal_naive", "persistence", "origin_nowcast"]:
            print(f"  {m:15s}: {r['in_season'][m]}")
