"""Chile blueberry orchard structure from the Catastro Frutícola (CIREN-ODEPA).

Free open data on datos.odepa.gob.cl: per-block records (anonymised holding x
block) with species, variety, PLANTING YEAR, irrigation, #trees and hectares,
by region/comuna. NOT in the free data (despite the Part 3 proposal): production
destination, yield, named entity (razon social), or georeferencing/rol -- those
are the paid CIREN directory, and even its GIS/rol content is unverified.

The census is run region-by-region on a ~3-year rotation, so each year-file
covers different regions (verified: 2019/2022/2024 are the comprehensive
blueberry years). We STITCH the latest survey per region into one coherent
structural snapshot. The value here is the planting-age structure -> a forward
capacity signal (capacity.py), which is exactly what Part 1's flow signals lacked.
"""
from __future__ import annotations

import datetime as _dt
import json

import pandas as pd
import requests

_CKAN = "https://datos.odepa.gob.cl/api/3/action"
_PACKAGE = "catastro-fruticola"
_HEADERS = {"User-Agent": "Mozilla/5.0 (uk-blueberry-nowcast/0.1)"}
_SPECIES = "Arándano Americano"      # exact Catastro label (CKAN q drops accents)


def _to_float(raw) -> float:
    if raw in (None, ""):
        return 0.0
    return float(str(raw).replace(".", "").replace(",", "."))


def _year_resources() -> dict[int, str]:
    pkg = requests.get(f"{_CKAN}/package_show", params={"id": _PACKAGE},
                       headers=_HEADERS, timeout=40).json()["result"]
    out = {}
    for res in pkg["resources"]:
        if res.get("datastore_active") and "año" in res.get("name", ""):
            try:
                out[int(res["name"].split()[-1])] = res["id"]
            except ValueError:
                continue
    return out


def _fetch_blueberry(resource_id: str) -> list[dict]:
    rows, off = [], 0
    while True:
        res = requests.get(
            f"{_CKAN}/datastore_search",
            params={"resource_id": resource_id,
                    "filters": json.dumps({"Especie": _SPECIES}),
                    "limit": 1000, "offset": off},
            headers=_HEADERS, timeout=60).json()["result"]
        rows.extend(res["records"])
        if off + 1000 >= res["total"]:
            break
        off += 1000
    return rows


def fetch_all_vintages(year_min: int = 2015) -> pd.DataFrame:
    """All blueberry blocks across every survey year (no stitching).

    Keeping every vintage is what lets capacity.py see ORCHARD REMOVALS between
    surveys (the -21% southern-belt decline 2019->2024) rather than only the
    maturation of a single snapshot. Columns as fetch_stitched.
    """
    resources = _year_resources()
    frames = []
    for year, rid in resources.items():
        if year < year_min:
            continue
        for r in _fetch_blueberry(rid):
            try:
                py = int(r["Anio plantacion"])
            except (ValueError, TypeError):
                py = None
            frames.append({
                "survey_year": year, "region": r["Region"],
                "comuna": r.get("Comuna", ""), "variedad": r.get("Variedad", ""),
                "planting_year": py, "hectares": _to_float(r["Superficie (ha)"]),
                "trees": _to_float(r.get("Numero de arboles", 0)),
            })
    return pd.DataFrame(frames)


def fetch_stitched(year_min: int = 2015) -> pd.DataFrame:
    """One blueberry snapshot: each region from its most recent survey year.

    Columns: survey_year, region, comuna, variedad, planting_year, hectares, trees.
    """
    resources = _year_resources()
    frames = []
    for year, rid in resources.items():
        if year < year_min:
            continue
        rows = _fetch_blueberry(rid)
        for r in rows:
            try:
                py = int(r["Anio plantacion"])
            except (ValueError, TypeError):
                py = None
            frames.append({
                "survey_year": year,
                "region": r["Region"],
                "comuna": r.get("Comuna", ""),
                "variedad": r.get("Variedad", ""),
                "planting_year": py,
                "hectares": _to_float(r["Superficie (ha)"]),
                "trees": _to_float(r.get("Numero de arboles", 0)),
            })
    df = pd.DataFrame(frames)
    if df.empty:
        return df
    # Stitch: keep each region's most recent survey year only.
    latest = df.groupby("region")["survey_year"].transform("max")
    return df[df["survey_year"] == latest].reset_index(drop=True)


if __name__ == "__main__":
    df = fetch_stitched()
    print(f"blueberry blocks (stitched): {len(df)}  total ha: {df['hectares'].sum():.0f}")
    by = df.groupby(["region", "survey_year"])["hectares"].sum().sort_values(ascending=False)
    print(by.head(10).round(0).to_string())
