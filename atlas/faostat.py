"""Global blueberry area / production / yield from FAOSTAT -- the production base
layer (what Comtrade is to trade, FAOSTAT is to growing).

One free source carries harvested area (ha), production (t) and yield for blueberries
(FAOSTAT item 552) for *every reporting country*, annually back to 1961. So the
"how much is grown, where" axis is a single sweep, not 15 national censuses -- those
(Catastro, ESYRCE, NASS, SIAP, ...) become finer *overlays* (variety, planting-year,
sub-national) layered on top, added selectively.

The JSON API is now auth-gated (401), but the **bulk** normalized CSV is open and
small (~33 MB): we download the QCL zip, keep item 552, drop FAO's regional/economic
aggregates (Area Code >= 5000), and pivot to one row per country-year. yield_t_ha is
recomputed as production/area for cleanliness. Committed to
`data/atlas/faostat_blueberry.csv`. Caveat: FAO area for the US/Canada includes
wild lowbush, so it dwarfs cultivated-only origins -- read alongside the trade grid.
"""
from __future__ import annotations

import csv
import io
import urllib.request
import zipfile

import pandas as pd

from atlas import ATLAS_DIR, hs_codes

CACHE = ATLAS_DIR / "faostat_blueberry.csv"
BULK_URL = ("https://bulks-faostat.fao.org/production/"
            "Production_Crops_Livestock_E_All_Data_(Normalized).zip")
ITEM_CODE = "552"                                   # FAOSTAT "Blueberries" (default)


def _cache(commodity: str) -> "object":
    """Per-commodity cache path -- blueberry keeps the original filename (Phase 4)."""
    return CACHE if commodity == "blueberry" else ATLAS_DIR / f"faostat_{commodity}.csv"
_ELEMENTS = {"5312": "area_ha", "5510": "production_t", "5419": "yield_raw"}
_AGG_MIN_CODE = 5000                                # FAO area codes >= 5000 are aggregates
_COLS = ["year", "m49", "country", "area_ha", "production_t", "yield_t_ha"]


def _is_country(row: dict) -> bool:
    try:
        return int(row.get("Area Code", 0)) < _AGG_MIN_CODE
    except (TypeError, ValueError):
        return False


def _rows_to_df(rows: list[dict], item_code: str = ITEM_CODE) -> pd.DataFrame:
    """Pivot normalized FAOSTAT rows for an item to one row per country-year (offline-testable)."""
    acc: dict[tuple, dict] = {}
    for r in rows:
        if r.get("Item Code") != item_code or not _is_country(r):
            continue
        col = _ELEMENTS.get(str(r.get("Element Code")))
        if col is None:
            continue
        val = r.get("Value")
        if val in (None, ""):
            continue
        key = (int(r["Year"]), r.get("Area Code (M49)", "").strip("'"), r.get("Area"))
        acc.setdefault(key, {})[col] = float(val)
    out = []
    for (year, m49, country), cells in acc.items():
        area = cells.get("area_ha", 0.0)
        prod = cells.get("production_t", 0.0)
        out.append({"year": year, "m49": m49, "country": country,
                    "area_ha": round(area, 1), "production_t": round(prod, 1),
                    "yield_t_ha": round(prod / area, 3) if area > 0 else 0.0})
    df = pd.DataFrame(out, columns=_COLS)
    return df.sort_values(["year", "production_t"], ascending=[True, False]).reset_index(drop=True)


def refresh(url: str = BULK_URL, commodity: str = "blueberry") -> pd.DataFrame:
    """Download the FAOSTAT QCL bulk, filter to the commodity, (re)write its cache."""
    item = hs_codes.fao_item(commodity)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=180).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    name = next(n for n in z.namelist()
                if n.lower().endswith(".csv") and "normalized" in n.lower())
    rows = []
    with z.open(name) as f:
        rd = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"))
        for row in rd:
            if row.get("Item Code") == item:
                rows.append(row)
    df = _rows_to_df(rows, item)
    if df.empty:
        raise RuntimeError(f"no {commodity} rows parsed from FAOSTAT bulk")
    out = _cache(commodity)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df


def load(commodity: str = "blueberry") -> pd.DataFrame:
    out = _cache(commodity)
    if not out.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(out)


def top_producers(year: int | None = None, n: int = 15, commodity: str = "blueberry") -> pd.DataFrame:
    df = load(commodity)
    if df.empty:
        return df
    year = year or int(df["year"].max())
    return df[df["year"] == year].head(n).reset_index(drop=True)


if __name__ == "__main__":                          # python -m atlas.faostat
    df = refresh()
    yr = int(df["year"].max())
    print(f"cached {len(df)} country-year rows -> {CACHE}")
    print(f"\ntop blueberry producers {yr} (FAO; incl. wild for US/CA):")
    print(top_producers(yr)[["country", "area_ha", "production_t", "yield_t_ha"]]
          .to_string(index=False))
