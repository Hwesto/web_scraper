"""HS-code registry: commodity → HS6 + national CN8/CN10/HTS splits.

This is the join key for the whole atlas and the lever for the other-fruit
extension (Phase 4 = swap the HS code, keep the machine). UN Comtrade speaks
HS6 (081040 = genus-Vaccinium fresh), so the global flow+price matrix is keyed
there; national customs (UK/EU CN8, US HTS10) split finer, and only some of
those splits are the *commercial* blueberry line — e.g. UK 08104050 is
cultivated blueberry + large cranberry, while 08104010 is cowberry (excluded).

Committed to `data/atlas/hs_codes.csv`. Blueberry rows are verified against the
live HMRC/Comtrade codes; other fruits are HS6 seeds for the extension, marked
`verified=no` until catalogued.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "hs_codes.csv"
_COLS = ["commodity", "hs6", "jurisdiction", "national_code", "level",
         "fresh", "description", "verified", "note"]

# The reference commodity: everything else is the same machine with this swapped.
DEFAULT_COMMODITY = "blueberry"


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE, dtype={"national_code": str, "hs6": str})


def hs6(commodity: str = DEFAULT_COMMODITY, fresh: str = "fresh") -> str:
    """The HS6 line for a commodity — the Comtrade sweep key. Raises if unknown."""
    df = load()
    sub = df[(df["commodity"] == commodity) & (df["fresh"] == fresh)]
    if sub.empty:
        raise KeyError(f"no HS6 for commodity={commodity!r} fresh={fresh!r}")
    return str(sub["hs6"].iloc[0])


def national_codes(commodity: str = DEFAULT_COMMODITY,
                   jurisdiction: str | None = None) -> pd.DataFrame:
    """National customs splits (CN8/HTS10) for a commodity, optionally one jurisdiction."""
    df = load()
    sub = df[(df["commodity"] == commodity) & (df["level"] != "HS6")]
    if jurisdiction is not None:
        sub = sub[sub["jurisdiction"] == jurisdiction]
    return sub.reset_index(drop=True)


def commodities(verified_only: bool = False) -> list[str]:
    df = load()
    if verified_only:
        df = df[df["verified"] == "yes"]
    return sorted(df["commodity"].unique())


if __name__ == "__main__":                             # python -m atlas.hs_codes
    print(f"blueberry HS6 = {hs6()}")
    print(national_codes().to_string(index=False))
