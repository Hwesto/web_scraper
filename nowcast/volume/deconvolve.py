"""Netherlands re-export de-convolution (spec section 2b).

HMRC records some UK imports as arriving FROM the Netherlands that are really
deep-sea fruit (Peru/Chile) trans-shipped through Rotterdam. Counting NL as EU
supply on top of the deep-sea origin double-counts the same berries.

Without consignee-level data the split cannot be observed, so this is an explicit
heuristic, tagged 'aggregate' and configurable: the portion of NL->UK volume that
co-moves with the deep-sea counter-season (roughly Nov-Mar) is treated as
re-export and reattributed pro-rata to Peru/Chile by their share that month; the
residual stays as genuine NL/EU supply. The default fraction is a documented
assumption, not a measurement -- surfaced so it is never mistaken for truth.
"""
from __future__ import annotations

import pandas as pd

# Months when Southern-Hemisphere deep-sea fruit dominates and is most likely to
# transit Rotterdam (UK counter-season).
DEEP_SEA_MONTHS = {11, 12, 1, 2, 3}
DEFAULT_REEXPORT_FRACTION = 0.5      # assumption: half of NL->UK in those months


def deconvolve_netherlands(monthly_by_origin: pd.DataFrame,
                           reexport_fraction: float = DEFAULT_REEXPORT_FRACTION
                           ) -> pd.DataFrame:
    """monthly_by_origin: index=month (Timestamp), columns include
    Netherlands, Peru, Chile (tonnes). Returns the same frame with NL reduced and
    Peru/Chile increased by the reattributed re-export volume.

    Mass is conserved: total across origins is unchanged.
    """
    df = monthly_by_origin.copy()
    if "Netherlands" not in df.columns:
        return df
    for col in ("Peru", "Chile"):
        if col not in df.columns:
            df[col] = 0.0

    for ts in df.index:
        if ts.month not in DEEP_SEA_MONTHS:
            continue
        nl = df.at[ts, "Netherlands"]
        reexport = nl * reexport_fraction
        deep = df.at[ts, "Peru"] + df.at[ts, "Chile"]
        if reexport <= 0 or deep <= 0:
            continue
        df.at[ts, "Netherlands"] = nl - reexport
        df.at[ts, "Peru"] += reexport * df.at[ts, "Peru"] / deep
        df.at[ts, "Chile"] += reexport * df.at[ts, "Chile"] / deep
    return df
