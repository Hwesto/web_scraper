"""Force every source to net kilograms (spec section 3).

HMRC NetMass and ODEPA 'Kilo neto' already arrive in kg/tonnes, so for the free
build these conversions are mostly latent -- but they are the single point where
box/punnet/FOB sources get normalised, so the table lives here and is used by
any source that reports a non-kg unit. Always net product weight, not gross.
"""
from __future__ import annotations

# Multiplicative factors: value_in_unit * factor = kilograms.
TO_KG = {
    "kg": 1.0,
    "tonne": 1000.0,
    "mt": 1000.0,
    "chile_box": 8.2,          # Chilean export box
    "us_flat_12x1pint": 4.08,  # US flat, 12 x 1-pint
}

# Punnet/clamshell: read pack grams directly.
PUNNET_GRAMS = {"125g": 0.125, "150g": 0.150, "200g": 0.200}


def to_kg(value: float, unit: str) -> float:
    key = unit.strip().lower()
    if key in TO_KG:
        return value * TO_KG[key]
    if key in PUNNET_GRAMS:
        return value * PUNNET_GRAMS[key]
    raise ValueError(f"unknown unit {unit!r}; add it to units.TO_KG")


def fob_value_to_kg(fob_value_usd: float, fob_usd_per_kg: float) -> float:
    """FOB-implied volume: value / FOB-USD-per-kg (spec section 3)."""
    if fob_usd_per_kg <= 0:
        raise ValueError("fob_usd_per_kg must be positive")
    return fob_value_usd / fob_usd_per_kg
