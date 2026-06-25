"""Symmetric turning-point test for the ODEPA origin-export lead.

The one signal labelled a 'positive' (Chile origin-export, corr 0.92) never faced
the walk-forward turning-point bar the four negatives did. A high lagged
correlation can be mostly shared seasonality, which seasonal-naive already owns.
This puts ODEPA export through the IDENTICAL gauntlet: does it add directional
skill on the HMRC-import ANOMALY (deviation from seasonal-naive), out-of-sample?

Two framings, both honest:
  - lag1: predict HMRC import month M from ODEPA export month M-1 (a mechanical
    voyage lead -- export has already departed, so no timeliness assumption).
  - contemp: predict import M from export M (independent same-month measure;
    only an edge if ODEPA prints no later than HMRC).
Scale (HMRC/ODEPA ~0.89, the 12% transhipment gap) is calibrated on train only.
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from ..benchmarks import persistence, seasonal_naive
from ..store import vintage
from . import metrics


def _odepa_chile() -> pd.Series:
    f = vintage.latest("odepa_chile_uk_exports")
    f = f[f["key"] == "Chile"].copy()
    f["d"] = pd.to_datetime(f["ref_period"])
    return f.set_index("d")["value"].sort_index()


def _hmrc_chile() -> pd.Series:
    f = vintage.latest("hmrc_blueberry_imports")
    f = f[f["key"] == "Chile"].copy()
    f["d"] = pd.to_datetime(f["ref_period"])
    return f.set_index("d")["value"].sort_index()


def run(min_train: int = 24, imp: pd.Series | None = None,
        exp: pd.Series | None = None) -> dict:
    imp = _hmrc_chile() if imp is None else imp
    exp = _odepa_chile() if exp is None else exp
    months = pd.date_range(min(imp.index.min(), exp.index.min()),
                           imp.index.max(), freq="MS")
    imp = imp.reindex(months, fill_value=0.0)
    exp = exp.reindex(months, fill_value=0.0)

    rows = []
    for i in range(min_train, len(months)):
        M = months[i]
        train_imp = imp.iloc[:i]
        train_exp = exp.iloc[:i]
        # scale calibrated on train overlap only (no look-ahead)
        ov = pd.concat([train_imp.rename("i"), train_exp.rename("e")], axis=1)
        ov = ov[(ov["e"] > 0)]
        scale = float(ov["i"].sum() / ov["e"].sum()) if ov["e"].sum() > 0 else 1.0

        norm = seasonal_naive(train_imp, 1)                 # same month last year
        rec = {
            "month": f"{M.year}-{M.month:02d}", "actual": float(imp.iloc[i]),
            "seasonal_norm": norm,
            "seasonal_naive": norm,
            "persistence": persistence(train_imp, 1),
            "odepa_lag1": scale * float(exp.iloc[i - 1]),   # export M-1 -> import M
            "odepa_contemp": scale * float(exp.iloc[i]),    # export M  -> import M
        }
        rows.append(rec)
    df = pd.DataFrame(rows)

    def score(sub: pd.DataFrame, label: str) -> dict:
        actual = sub["actual"].values
        norm = sub["seasonal_norm"].values
        base = metrics.accuracy(actual, sub["seasonal_naive"].values)["mae"]
        res = {"label": label, "n": len(sub)}
        for model in ["seasonal_naive", "persistence", "odepa_lag1", "odepa_contemp"]:
            pred = sub[model].values
            acc = metrics.accuracy(actual, pred)
            res[model] = {
                "mae": round(acc["mae"], 0),
                "dir_skill_%": round(metrics.directional_skill(actual, pred, norm), 1),
                "skill_vs_snaive_%": round(metrics.skill_vs(acc["mae"], base), 1),
            }
        return res

    # In-season = months whose seasonal norm is materially non-zero (Chile Nov-Apr).
    inseason = df[df["seasonal_norm"] >= 100.0]
    return {"all": score(df, "all months"),
            "in_season": score(inseason, "in-season only"),
            "table": df}


if __name__ == "__main__":
    r = run()
    for key in ["all", "in_season"]:
        s = r[key]
        print(f"\n=== {s['label']} (n={s['n']}) ===")
        for m in ["seasonal_naive", "persistence", "odepa_lag1", "odepa_contemp"]:
            print(f"  {m:16s}: {s[m]}")
