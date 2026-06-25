"""Planting-age -> bearing-capacity model (the forward structural signal).

A highbush blueberry bush yields ~nothing in its first 1-2 years and ramps to
full bearing by ~year 6. Applying that curve to the Catastro's area-by-planting-
year converts a static orchard snapshot into a CAPACITY TRAJECTORY: as young
blocks age, bearing capacity rises even with no new plantings. This is the
season-level structural forecast Part 1 lacked -- it knows next year will NOT
equal this year, and in which direction.

The yield-by-age curve is an agronomic assumption (documented, adjustable), not a
measurement; the validation (forecast.py) checks whether the resulting capacity
trajectory actually tracks realised Chile->UK exports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Fraction of mature yield by vine age in years (highbush blueberry, indicative).
_AGE_YIELD = {0: 0.0, 1: 0.05, 2: 0.20, 3: 0.45, 4: 0.70, 5: 0.90}
_MATURE = 1.0          # age >= 6
_SENESCENCE_AGE = 18   # beyond this, assume gradual decline (kept simple: flat)


def yield_fraction(age: int) -> float:
    if age < 0:
        return 0.0
    if age >= 6:
        return _MATURE
    return _AGE_YIELD[age]


# Fresh-UK suitability by variety (0..1). The UK is a long sea-freight market, so
# post-harvest firmness is decisive: old/soft varieties are diverted to frozen,
# newer firm cultivars carry the fresh corridor. This is an explicit, adjustable
# heuristic grounded in the Chilean variety-renewal literature -- NOT a measurement.
_VARIETY_FRESH_WEIGHT = {
    # newer / firm / club -> fresh export
    "blue ribbon": 0.95, "suziblue": 0.9, "ventura": 0.85, "cargo": 0.9,
    "sekoya": 0.95, "eureka": 0.95, "stella": 0.9, "draper": 0.9, "top shelf": 0.95,
    "last call": 0.9, "magnolia": 0.85, "bianca": 0.9, "rocio": 0.9, "kirra": 0.9,
    # mid workhorses (still fresh-exported but aging)
    "legacy": 0.6, "duke": 0.6, "star": 0.6, "emerald": 0.65, "jewel": 0.6,
    "snowchaser": 0.65, "camellia": 0.5,
    # old / soft / rabbiteye -> largely frozen/processing
    "brigitta": 0.25, "o'neal": 0.3, "oneal": 0.3, "elliot": 0.2, "elliott": 0.2,
    "bluecrop": 0.3, "misty": 0.3, "brightwell": 0.2, "ochlockonee": 0.2,
    "ochcklonee": 0.2, "reveille": 0.25, "powderblue": 0.2, "aurora": 0.4,
}
_DEFAULT_WEIGHT = 0.5


def variety_weight(name: str) -> float:
    key = (name or "").strip().lower()
    for variety, w in _VARIETY_FRESH_WEIGHT.items():
        if variety in key:
            return w
    return _DEFAULT_WEIGHT


def _nearest_survey(blocks_all: pd.DataFrame, season: int) -> pd.DataFrame:
    """Blocks from the most recent survey on or before `season` (else earliest)."""
    surveys = sorted(blocks_all["survey_year"].unique())
    pick = max([s for s in surveys if s <= season], default=surveys[0])
    return blocks_all[blocks_all["survey_year"] == pick]


def fresh_capacity(blocks_all: pd.DataFrame, season: int, use_variety: bool = True) -> float:
    """Vintage-aware, optionally variety-weighted bearing capacity for `season`.

    Uses the ACTUAL surveyed area nearest that season (capturing removals between
    surveys), aged by the yield curve, and -- when use_variety -- scaled by each
    block's variety fresh-UK suitability so soft/frozen-bound area is discounted.
    """
    df = _nearest_survey(blocks_all, season).dropna(subset=["planting_year"])
    ages = (season - df["planting_year"].astype(int)).map(yield_fraction)
    weights = df["variedad"].map(variety_weight) if use_variety else 1.0
    return float((df["hectares"] * ages * weights).sum())


def comprehensive_years(blocks_all: pd.DataFrame, min_ha: float = 5000.0) -> list[int]:
    """Survey years with near-national coverage (large total area). Partial-
    coverage year-files (1-2 regions) must NOT be used as snapshots -- doing so
    makes the index measure survey COVERAGE, not capacity (a spurious signal)."""
    tot = blocks_all.groupby("survey_year")["hectares"].sum()
    return sorted(tot[tot >= min_ha].index)


def interpolated_capacity(blocks_all: pd.DataFrame, seasons, use_variety: bool = True
                          ) -> pd.Series:
    """Capacity index by season: anchored at comprehensive survey years (actual
    area x maturation x variety) and linearly interp/extrapolated between them.
    This removes the coverage artefact and yields a smooth, honest trajectory."""
    years = comprehensive_years(blocks_all)
    anchors = {}
    for y in years:
        snap = blocks_all[blocks_all["survey_year"] == y].dropna(subset=["planting_year"])
        ages = (y - snap["planting_year"].astype(int)).map(yield_fraction)
        w = snap["variedad"].map(variety_weight) if use_variety else 1.0
        anchors[y] = float((snap["hectares"] * ages * w).sum())
    ay = np.array(sorted(anchors)); av = np.array([anchors[y] for y in ay])
    # np.interp holds the endpoints flat; extend the last slope for extrapolation.
    out = {}
    for s in seasons:
        if s <= ay[0]:
            out[s] = av[0]
        elif s >= ay[-1]:
            slope = (av[-1] - av[-2]) / (ay[-1] - ay[-2]) if len(ay) >= 2 else 0.0
            out[s] = av[-1] + slope * (s - ay[-1])
        else:
            out[s] = float(np.interp(s, ay, av))
    return pd.Series(out)


def bearing_capacity(blocks: pd.DataFrame, season: int) -> float:
    """Bearing-capacity-equivalent hectares of the snapshot evaluated in `season`
    (each block aged season - planting_year)."""
    df = blocks.dropna(subset=["planting_year"])
    ages = season - df["planting_year"].astype(int)
    frac = ages.map(yield_fraction)
    return float((df["hectares"] * frac).sum())


def capacity_trajectory(blocks: pd.DataFrame, seasons: range) -> pd.Series:
    """Bearing-capacity index per season (ha-equivalent). Seasons after the
    survey age the SAME blocks (no new plantings) -> a conservative lower bound
    on capacity growth from maturation alone."""
    return pd.Series({s: bearing_capacity(blocks, s) for s in seasons}, name="capacity_ha")


def planted_area_trajectory(blocks: pd.DataFrame, seasons: range) -> pd.Series:
    """Total planted (not yet-bearing-weighted) ha existing by each season --
    i.e. cumulative area planted up to that year."""
    df = blocks.dropna(subset=["planting_year"])
    return pd.Series(
        {s: float(df.loc[df["planting_year"].astype(int) <= s, "hectares"].sum())
         for s in seasons}, name="planted_ha")
