"""Re-aimed Part 1 test: can the Catastro capacity trajectory beat seasonal-naive
on the DIRECTION of season-over-season Chile->UK export change (turning points)?

Seasonal-naive predicts next season = last season -> it can NEVER call a turning
point (predicted change is always 0). The planting-age capacity index predicts a
direction. We score: (a) directional hit-rate of the capacity tilt on the sign of
realised YoY export change, and (b) correlation of capacity growth with realised
export growth. Honest caveat: the structural signal is season-level and the
Catastro is one dominant vintage, so there are only a handful of transitions --
low statistical power, reported as such.
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from ..store import vintage
from . import capacity
from .data.catastro import fetch_stitched

# Southern-hemisphere blueberry campaign months that land in UK by season Y.
_SEASON_MONTHS = [(11, -1), (12, -1), (1, 0), (2, 0), (3, 0), (4, 0)]


def export_season_totals() -> pd.Series:
    """ODEPA Chile->UK tonnes aggregated into campaign seasons (label = end year)."""
    frame = vintage.latest("odepa_chile_uk_exports")
    frame = frame[frame["key"] == "Chile"].copy()
    frame["d"] = pd.to_datetime(frame["ref_period"])
    m = frame.set_index("d")["value"]
    totals: dict[int, float] = {}
    for ts, val in m.items():
        for month, yr_off in _SEASON_MONTHS:
            if ts.month == month:
                season = ts.year - yr_off
                totals[season] = totals.get(season, 0.0) + float(val)
    return pd.Series(totals).sort_index()


def turning_point_test(blocks: pd.DataFrame | None = None) -> dict:
    blocks = fetch_stitched() if blocks is None else blocks
    exports = export_season_totals()
    seasons = [s for s in exports.index if exports[s] > 0]
    cap = capacity.capacity_trajectory(blocks, range(min(seasons) - 1, max(seasons) + 1))

    rows = []
    for s in seasons:
        if (s - 1) not in exports.index or (s - 1) not in cap.index or s not in cap.index:
            continue
        actual_chg = exports[s] - exports[s - 1]
        naive_chg = 0.0                                   # seasonal-naive: no change
        cap_growth = cap[s] / cap[s - 1] - 1.0 if cap[s - 1] else 0.0
        tilt_pred = exports[s - 1] * (1 + cap_growth)
        tilt_chg = tilt_pred - exports[s - 1]
        rows.append({
            "season": s, "actual": exports[s], "actual_chg": actual_chg,
            "cap_growth_%": 100 * cap_growth,
            "tilt_pred": tilt_pred, "tilt_chg": tilt_chg,
            "naive_pred": exports[s - 1],
            "dir_hit_tilt": int(np.sign(tilt_chg) == np.sign(actual_chg)),
        })
    res = pd.DataFrame(rows)
    out = {"table": res, "n": len(res)}
    if len(res):
        out["dir_hitrate_tilt_%"] = round(100 * res["dir_hit_tilt"].mean(), 1)
        out["mae_tilt"] = float(np.mean(np.abs(res["tilt_pred"] - res["actual"])))
        out["mae_naive"] = float(np.mean(np.abs(res["naive_pred"] - res["actual"])))
        if res["cap_growth_%"].std() > 0 and res["actual_chg"].std() > 0:
            out["corr_capgrowth_actualchg"] = round(
                float(res["cap_growth_%"].corr(res["actual_chg"])), 2)
    return out


def _score(exports: pd.Series, cap: pd.Series, seasons: list[int]) -> dict:
    """Tilt seasonal-naive by capacity growth; score direction + MAE vs naive."""
    rows = []
    for s in seasons:
        if (s - 1) not in exports.index or (s - 1) not in cap.index or s not in cap.index:
            continue
        actual_chg = exports[s] - exports[s - 1]
        growth = cap[s] / cap[s - 1] - 1.0 if cap[s - 1] else 0.0
        tilt = exports[s - 1] * (1 + growth)
        rows.append({"season": s, "actual": exports[s], "actual_chg": actual_chg,
                     "cap_growth_%": 100 * growth, "tilt": tilt,
                     "naive": exports[s - 1],
                     "dir_hit": int(np.sign(tilt - exports[s - 1]) == np.sign(actual_chg))})
    r = pd.DataFrame(rows)
    if r.empty:
        return {"n": 0}
    return {
        "n": len(r), "table": r,
        "dir_hitrate_%": round(100 * r["dir_hit"].mean(), 1),
        "mae_tilt": round(float(np.mean(np.abs(r["tilt"] - r["actual"]))), 0),
        "mae_naive": round(float(np.mean(np.abs(r["naive"] - r["actual"]))), 0),
        "corr_growth_chg": round(float(r["cap_growth_%"].corr(r["actual_chg"]))
                                 if r["cap_growth_%"].std() > 0 else float("nan"), 2),
    }


def compare_models() -> dict:
    """v1 (maturation-only from one snapshot) vs v2 (vintage+variety fresh
    capacity) vs seasonal-naive, on the same seasons."""
    from .data.catastro import fetch_all_vintages, fetch_stitched

    exports = export_season_totals()
    seasons = [s for s in exports.index if exports[s] > 0 and (s - 1) in exports.index]
    rng = range(min(seasons) - 1, max(seasons) + 1)

    snapshot = fetch_stitched()
    cap_v1 = capacity.capacity_trajectory(snapshot, rng)

    allv = fetch_all_vintages()
    # Comprehensive-years-only, interpolated (removes the survey-coverage artefact).
    cap_v2 = capacity.interpolated_capacity(allv, rng, use_variety=True)
    cap_v2_novar = capacity.interpolated_capacity(allv, rng, use_variety=False)

    return {
        "comprehensive_years": capacity.comprehensive_years(allv),
        "v1_maturation_only": _score(exports, cap_v1, seasons),
        "v2_interp_vintage_only": _score(exports, cap_v2_novar, seasons),
        "v2_interp_vintage_variety": _score(exports, cap_v2, seasons),
    }


if __name__ == "__main__":
    res = compare_models()
    print("comprehensive survey years:", res.pop("comprehensive_years"))
    for name, r in res.items():
        summ = {k: v for k, v in r.items() if k != "table"}
        print(f"{name}: {summ}")
    print("\n--- v2 interp (vintage+variety) detail ---")
    print(res["v2_interp_vintage_variety"]["table"].round(1).to_string(index=False))
