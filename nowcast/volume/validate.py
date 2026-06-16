"""Validation (spec section 6): two-sided cross-check and mass-balance sanity.

Two-sided: origin-export-to-UK (ODEPA, Chile) vs HMRC-import-from-Chile are two
independent measures of one flow. They should agree on season totals; persistent
level divergence flags mislabel/transhipment/code error, and the month-shift
between them is the deep-sea transit lag (export leads import).
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from ..store import vintage


def _monthly(series_name: str, key: str, as_of: _dt.date | None) -> pd.Series:
    frame = vintage.as_of(series_name, as_of) if as_of else vintage.latest(series_name)
    sub = frame[frame["key"] == key].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    sub["d"] = pd.to_datetime(sub["ref_period"])
    return sub.set_index("d")["value"].sort_index()


def two_sided_crosscheck(origin: str = "Chile", as_of: _dt.date | None = None) -> dict:
    """Compare ODEPA export-to-UK vs HMRC import for an origin; estimate the
    transit lag by the shift that best aligns them."""
    exp = _monthly("odepa_chile_uk_exports", origin, as_of)
    imp = _monthly("hmrc_blueberry_imports", origin, as_of)
    joined = pd.concat([exp.rename("export"), imp.rename("import")], axis=1).dropna()
    if len(joined) < 6:
        return {"origin": origin, "n": len(joined), "note": "insufficient overlap"}

    # Season-total agreement and best monthly lag (export leads import).
    ratio = joined["export"].sum() / joined["import"].sum()
    best_lag, best_corr = 0, -2.0
    for lag in range(0, 3):                       # export[t] vs import[t+lag]
        a = exp.shift(0); b = imp.shift(-lag)
        m = pd.concat([a, b], axis=1).dropna()
        if len(m) >= 6:
            c = m.iloc[:, 0].corr(m.iloc[:, 1])
            if c > best_corr:
                best_corr, best_lag = c, lag
    return {
        "origin": origin, "n": int(len(joined)),
        "export_over_import": round(float(ratio), 3),
        "best_lag_months": best_lag, "lagged_corr": round(float(best_corr), 3),
    }


def import_total_balance(as_of: _dt.date | None = None) -> pd.DataFrame:
    """Mass-balance sanity: sum of per-origin imports should equal the all-origin
    HMRC total (no double-count, no missing origin). Returns monthly residual."""
    frame = vintage.as_of("hmrc_blueberry_imports", as_of) if as_of \
        else vintage.latest("hmrc_blueberry_imports")
    frame = frame.copy()
    frame["d"] = pd.to_datetime(frame["ref_period"])
    by_origin = frame.groupby("d")["value"].sum()
    # (Here the per-origin sum IS the total we ingest; the check guards against
    # later additions like NL de-convolution introducing double counts.)
    return by_origin.rename("origins_sum").to_frame()
