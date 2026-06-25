"""Phase-2a signal probe: does Sentinel-2 growing-season NDVI over Chilean blueberry
regions track Chile→UK exports? No GDAL (sandbox MITM blocks it) -- reads COG
overviews via tifffile+fsspec over the requests/aiohttp stack that trusts the
egress CA. Coarse on purpose (~80 m overview); this is a GO/NO-GO, not the build.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.request

import fsspec
import numpy as np
import pandas as pd
import tifffile
from pyproj import Transformer

from deep.store import vintage

STAC = "https://earth-search.aws.element84.com/v1/search"
# blueberry AOIs (small ~8 km boxes in the heart of the producing comunas)
AOIS = {
    "Ñuble (Chillán)":     (-72.20, -36.70, -72.05, -36.55),
    "Bío Bío (Los Ángeles)": (-72.42, -37.52, -72.27, -37.37),
    "Maule (Linares)":     (-71.65, -35.90, -71.50, -35.75),
}
_CLOUD_SCL = {0, 1, 3, 8, 9, 10, 11}      # nodata/defective/shadow/cloud/cirrus/snow


def _stac(bbox, start, end, limit=12):
    body = json.dumps({"collections": ["sentinel-2-l2a"], "bbox": list(bbox),
                       "datetime": f"{start}/{end}", "limit": limit,
                       "query": {"eo:cloud_cover": {"lt": 60}}}).encode()
    req = urllib.request.Request(STAC, data=body,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60)).get("features", [])


def _read_aoi(href, epsg, bbox, target_m=80.0):
    """Read the COG overview nearest target_m and crop to bbox (WGS84) -> 2-D array."""
    with fsspec.open(href).open() as f:
        with tifffile.TiffFile(f) as tif:
            levels = tif.series[0].levels
            full_w = levels[0].shape[-1]
            gt = tif.geotiff_metadata
            sx, sy = gt["ModelPixelScale"][0], gt["ModelPixelScale"][1]
            tie = gt["ModelTiepoint"]; x0, y0 = tie[3], tie[4]
            # pick overview whose pixel size is closest to target_m
            lv = min(levels, key=lambda s: abs(sx * full_w / s.shape[-1] - target_m))
            arr = np.asarray(lv.asarray())
            px = sx * full_w / arr.shape[-1]            # overview pixel size (m)
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    xs, ys = tr.transform([bbox[0], bbox[2]], [bbox[1], bbox[3]])
    c0, c1 = sorted((int((min(xs) - x0) / px), int((max(xs) - x0) / px)))
    r0, r1 = sorted((int((y0 - max(ys)) / px), int((y0 - min(ys)) / px)))
    c0, r0 = max(c0, 0), max(r0, 0)
    return arr[r0:r1 + 1, c0:c1 + 1]


def _scene_ndvi(feat, bbox):
    a = feat["assets"]; epsg = feat["properties"]["proj:epsg"]
    red = _read_aoi(a["red"]["href"], epsg, bbox).astype("float32")
    nir = _read_aoi(a["nir"]["href"], epsg, bbox).astype("float32")
    scl = _read_aoi(a["scl"]["href"], epsg, bbox)
    # SCL is 20 m vs 10 m red/nir; resize SCL (nearest) to red shape
    if scl.shape != red.shape:
        ri = (np.linspace(0, scl.shape[0] - 1, red.shape[0])).round().astype(int)
        ci = (np.linspace(0, scl.shape[1] - 1, red.shape[1])).round().astype(int)
        scl = scl[ri][:, ci]
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
    clear = ~np.isin(scl, list(_CLOUD_SCL)) & np.isfinite(ndvi) & (ndvi > 0)
    if clear.sum() < 20:
        return None
    return float(np.median(ndvi[clear]))


def season_ndvi(year_end: int):
    """Peak growing-season (Dec(year_end-1)..Feb(year_end)) AOI-mean NDVI."""
    start = f"{year_end-1}-12-01T00:00:00Z"; end = f"{year_end}-02-20T23:59:59Z"
    aoi_vals = []
    for name, bbox in AOIS.items():
        best = None
        for feat in sorted(_stac(bbox, start, end),
                           key=lambda f: f["properties"].get("eo:cloud_cover", 100)):
            try:
                v = _scene_ndvi(feat, bbox)
            except Exception:                           # noqa: BLE001
                continue
            if v is not None:
                best = v; break                         # least-cloudy usable scene
        if best is not None:
            aoi_vals.append(best)
    return float(np.mean(aoi_vals)) if aoi_vals else np.nan


def uk_chile_season(year_end: int) -> float:
    """Chile→UK arrivals for the season landing in `year_end` (Jan–Apr, tonnes)."""
    v = vintage.latest("hmrc_blueberry_imports")
    v = v[v["key"] == "Chile"].copy(); v["d"] = pd.to_datetime(v["ref_period"])
    m = v[(v["d"] >= f"{year_end}-01-01") & (v["d"] <= f"{year_end}-04-30")]
    return float(m["value"].sum())


def main():
    rows = []
    for ye in range(2019, _dt.date.today().year + 1):
        ndvi = season_ndvi(ye)
        exp = uk_chile_season(ye)
        rows.append({"season_end": ye, "ndvi": round(ndvi, 3) if ndvi == ndvi else None,
                     "uk_chile_t": round(exp)})
        print(f"  {ye}: NDVI={ndvi:.3f}  UK-Chile(Jan-Apr)={exp:,.0f} t", flush=True)
    df = pd.DataFrame(rows).dropna()
    df.to_csv("/tmp/sentinel_probe.csv", index=False)
    _verdict(df)


def _verdict(df: pd.DataFrame) -> None:
    print(f"\nseasons with both: {len(df)}")
    if len(df) < 5:
        return
    y = df["season_end"].astype(float).values

    def detrend(v):                                    # strip the structural trend
        return v - np.polyval(np.polyfit(y, v, 1), y)
    raw = df["ndvi"].corr(df["uk_chile_t"], method="spearman")
    dd = pd.DataFrame({"n": detrend(df["ndvi"].values), "e": detrend(df["uk_chile_t"].values)})
    det = dd["n"].corr(dd["e"], method="spearman")
    print(f"Test A raw exports:          Spearman {raw:+.2f}")
    print(f"Test B detrended residual:   Spearman {det:+.2f}   <- the condition test")
    # verdict on Test B (the scope's real test); honest about small n
    if abs(det) >= 0.5:
        print(f"GO/NO-GO: cautious GO — condition signal present (Spearman {det:+.2f}), "
              f"but n={len(df)} is low power; a proper integrated metric + cropland mask "
              f"in 2b should firm it up.")
    else:
        print("GO/NO-GO: WEAK on the condition test too — reconsider before 2b.")


if __name__ == "__main__":
    main()
