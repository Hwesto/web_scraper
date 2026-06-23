"""M49 ↔ country-name lookup, from UN Comtrade's Reporters reference.

Comtrade's preview rows carry only the numeric reporter/partner code (the
`reporterDesc` field is null in preview), so every ranking and bilateral cell
needs this map to be human-readable. The reference is committed to
`data/atlas/country_codes.csv` (255 areas, M49 + ISO2/ISO3) and read offline;
`refresh()` re-pulls it from the live reference endpoint when needed.

Codes absent from the reference (e.g. 490 "Other Asia, nes", 568, 636) fall
back to `M49-<code>` so nothing is ever silently dropped.
"""
from __future__ import annotations

import csv
import json
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "country_codes.csv"
_REF = "https://comtradeapi.un.org/files/v1/app/reference/Reporters.json"
_COLS = ["m49", "name", "iso2", "iso3"]


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def name_map() -> dict[int, str]:
    df = load()
    return dict(zip(df["m49"].astype(int), df["name"]))


def name(code: int, m: dict[int, str] | None = None) -> str:
    m = name_map() if m is None else m
    return m.get(int(code), f"M49-{int(code)}")


def refresh(retries: int = 4) -> pd.DataFrame:
    """Re-pull the Comtrade reporter reference and rewrite the committed CSV."""
    import time
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(_REF, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                payload = json.load(r)
            break
        except Exception as e:                         # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"Reporters reference fetch failed: {last}")

    res = payload.get("results") or payload
    rows = []
    for x in res:
        code = x.get("reporterCode") or x.get("id")
        if code is None:
            continue
        rows.append({
            "m49": int(code),
            "name": x.get("reporterDesc") or x.get("text") or f"M49-{code}",
            "iso2": x.get("reporterCodeIsoAlpha2") or "",
            "iso3": x.get("reporterCodeIsoAlpha3") or "",
        })
    df = pd.DataFrame(rows, columns=_COLS).drop_duplicates("m49").sort_values("m49")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False, quoting=csv.QUOTE_MINIMAL)
    return df


if __name__ == "__main__":                             # python -m atlas.countries
    df = refresh()
    print(f"cached {len(df)} country codes -> {CACHE}")
