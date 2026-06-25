"""FAOSTAT — blueberry production by country (who *grows* the world's berries).

The trade map (comtrade_global) only sees cross-border flow, so big grow-it-
themselves markets look small as importers. This adds the supply side: FAOSTAT
QCL "Blueberries" production, latest two years (for y/y), countries only.

THE CHINA BLIND SPOT (documented, not a bug): China is widely reported (IBO and
trade press) as the world's largest blueberry producer, yet reports **no**
blueberry output to FAOSTAT — so no free dataset captures it. We flag this rather
than fake it. Source for China's scale is paid/industry (IBO).

Cache: data/market/global_production.csv (year, country, tonnes). FAOSTAT bulk is
annual + ~34 MB, so this is an occasional refresh, not part of the weekly grind.
"""
from __future__ import annotations

import csv
import io
import zipfile

import pandas as pd
import requests

from ..config import DATA_DIR

CACHE = DATA_DIR / "market" / "global_production.csv"
_BULK = ("https://bulks-faostat.fao.org/production/"
         "Production_Crops_Livestock_E_All_Data_(Normalized).zip")
_HEADERS = {"User-Agent": "uk-blueberry-atlas/0.1 (research)"}
# FAOSTAT regional/economic aggregates carry Area Code >= 5000; countries are below.
_AGG_FLOOR = 5000


def refresh(cache=CACHE) -> pd.DataFrame:
    """Download the FAOSTAT bulk, keep Blueberries production for real countries,
    cache the latest two years. Returns the tidy frame."""
    resp = requests.get(_BULK, headers=_HEADERS, timeout=240)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    name = next(n for n in zf.namelist() if n.endswith(".csv"))
    rows = []
    with zf.open(name) as fh:
        for r in csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1")):
            if r.get("Item") != "Blueberries" or r.get("Element") != "Production":
                continue
            try:
                area_code = int(r.get("Area Code") or 0)
                year = int(r["Year"])
                val = float(r["Value"] or 0)
            except (ValueError, TypeError):
                continue
            if area_code >= _AGG_FLOOR or val <= 0:      # drop regional aggregates
                continue
            rows.append({"year": year, "country": r["Area"], "tonnes": val})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    years = sorted(df["year"].unique())[-2:]             # latest two for y/y
    df = df[df["year"].isin(years)]
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["year", "tonnes"], ascending=[False, False]).to_csv(cache, index=False)
    return df


def load(cache=CACHE) -> pd.DataFrame:
    if not cache.exists():
        return pd.DataFrame(columns=["year", "country", "tonnes"])
    return pd.read_csv(cache)


# FAOSTAT names -> the short names used elsewhere on the board
_RENAME = {"United States of America": "United States", "Russian Federation": "Russia",
           "Netherlands (Kingdom of the)": "Netherlands", "China, mainland": "China"}

# Countries FAOSTAT omits but that are documented elsewhere. Sourced + dated, not
# fabricated — kept here as the single, citable override. China is the big one:
# it reports no blueberries to FAOSTAT despite being the world's largest grower.
MANUAL = {
    "China": {"tonnes": 525_000, "year": 2023,
              "source": "Produce Report / IBO (2023 est.)"},
}


def production_by_country(df: pd.DataFrame | None = None) -> dict:
    """{country: (tonnes, year, source)} — FAOSTAT latest year (source=None) plus
    the documented MANUAL overrides for countries FAOSTAT omits."""
    df = load() if df is None else df
    out: dict[str, tuple] = {}
    if not df.empty:
        df = df.copy()
        df["country"] = df["country"].replace(_RENAME)
        yr = int(df["year"].max())
        for x in df[df["year"] == yr].itertuples():
            out[x.country] = (float(x.tonnes), yr, None)
    for c, m in MANUAL.items():
        out.setdefault(c, (float(m["tonnes"]), m["year"], m["source"]))
    return out


def top_growers(n: int = 6, df: pd.DataFrame | None = None):
    """[(country, tonnes, yoy_pct)] for the latest year, prior year for y/y."""
    df = load() if df is None else df
    if df.empty:
        return []
    df = df.copy()
    df["country"] = df["country"].replace(_RENAME)
    yr = int(df["year"].max())
    cur = df[df["year"] == yr].sort_values("tonnes", ascending=False).head(n)
    prev = df[df["year"] == yr - 1].set_index("country")["tonnes"].to_dict()
    out = []
    for x in cur.itertuples():
        p = prev.get(x.country)
        yoy = (x.tonnes / p - 1) * 100 if p else float("nan")
        out.append((x.country, float(x.tonnes), yoy))
    return out


if __name__ == "__main__":
    out = refresh()
    print(f"wrote {len(out)} rows -> {CACHE}")
    for c, t, y in top_growers(8):
        print(f"  {c:18s} {t/1000:6.1f} kt   y/y {y:+.0f}%" if y == y else f"  {c:18s} {t/1000:6.1f} kt")
