"""Fused whole-market UK blueberry supply -- the year-round 'their market' view.

HMRC anchors every origin every month, so summing the per-origin reconciled
weekly series (Part 2 engine) gives a continuous UK supply series that is NEVER
blank -- live shipment shape on deep-sea lanes in season (Chile now, Peru next),
benchmarked elsewhere. Output: weekly UK total + per-origin contributions, with a
flag for which origins are on a live feed that week.
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from ..config import KG_PER_TONNE
from .series import build_origin_volume, _EXPORT_FEEDS
from . import tiering

# Origins modelled individually (~96% of UK imports); the rest -> "Other".
MAJORS = ["Morocco", "Peru", "South Africa", "Chile", "Spain", "Netherlands",
          "Poland", "Argentina", "Portugal"]
# Deep-sea lanes that can carry a 2-week origin-export nowcast lead.
DEEP_SEA = {"Peru", "Chile", "South Africa", "Argentina"}


def _hmrc_total_monthly(as_of: _dt.date | None, start: str) -> pd.Series:
    from ..backtest.replay import load_origin_series
    from ..store import vintage
    frame = (vintage.as_of("hmrc_blueberry_imports", as_of) if as_of
             else vintage.latest("hmrc_blueberry_imports")).copy()
    frame["d"] = pd.to_datetime(frame["ref_period"])
    s = frame[frame["d"] >= start].groupby("d")["value"].sum()
    return s


def _week_month(iso_week: str) -> str:
    y, w = iso_week.split("-W")
    thu = pd.Timestamp.fromisocalendar(int(y), int(w), 4)
    return f"{thu.year}-{thu.month:02d}"


def build_uk_total(as_of: _dt.date | None = None, start: str = "2022-01-01") -> dict:
    as_of = as_of or _dt.date.today()
    per_origin, live_weeks = {}, {}
    for origin in MAJORS:
        v = build_origin_volume(origin, as_of=as_of, start=start)
        if v.empty:
            continue
        v = v.set_index("iso_week")
        per_origin[origin] = v["volume_kg"]
        live_weeks[origin] = (v["confidence_tier"] == tiering.SHIPMENT)

    wide = pd.DataFrame(per_origin).fillna(0.0)
    wide["majors_total"] = wide.sum(axis=1)
    wide["month"] = [_week_month(w) for w in wide.index]

    # "Other" = HMRC all-origin total minus the majors, spread evenly across the
    # month's weeks (keeps the UK total reconciled to the whole-market control).
    total_m = _hmrc_total_monthly(as_of, start) * KG_PER_TONNE
    total_m.index = total_m.index.strftime("%Y-%m")
    majors_m = wide.groupby("month")["majors_total"].sum()
    other_m = (total_m.reindex(majors_m.index).fillna(0.0) - majors_m).clip(lower=0)
    wk_per_month = wide.groupby("month").size()
    wide["Other"] = [other_m.get(m, 0.0) / wk_per_month.get(m, 1) for m in wide["month"]]

    origin_cols = [c for c in wide.columns if c not in ("majors_total", "month")]
    wide["uk_total_kg"] = wide[origin_cols].sum(axis=1)
    wide["live_origins"] = [
        ",".join(o for o in live_weeks if live_weeks[o].get(w, False)) or "-"
        for w in wide.index]

    return {"weekly": wide.reset_index(), "origin_cols": origin_cols,
            "live_lanes_available": sorted(set(_EXPORT_FEEDS) & set(MAJORS)),
            "deep_sea": sorted(DEEP_SEA & set(MAJORS))}


if __name__ == "__main__":
    r = build_uk_total()
    w = r["weekly"]
    print(f"UK total weekly rows: {len(w)} | live feeds: {r['live_lanes_available']} "
          f"| deep-sea lanes: {r['deep_sea']}")
    cols = ["iso_week", "uk_total_kg"] + [c for c in ["Peru", "Chile", "Morocco",
            "Spain", "South Africa", "Other"] if c in w.columns] + ["live_origins"]
    print(w[cols].tail(14).round(0).to_string(index=False))
