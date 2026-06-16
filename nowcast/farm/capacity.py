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
