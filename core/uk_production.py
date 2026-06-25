"""UK domestic blueberry production from DEFRA Horticulture Statistics (annual).

The British-season supply Britain grows itself — production (kt), value (£m) and
yield (t/ha) by year. Area is suppressed by DEFRA (too few growers). Annual ODS on
gov.uk; parsed via zipfile (no odfpy dep). Manual refresh: bump REPORT_URL yearly.
"""
from __future__ import annotations

import io
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from nowcast.config import DATA_DIR

OUT = DATA_DIR / "market" / "uk_blueberry_production.csv"
REPORT_URL = ("https://assets.publishing.service.gov.uk/media/685ba429e9509f1a908eb16b/"
              "hort-dataset-24-20250626.ods")
_HDR = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)"}
_TBL = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_TXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_TABLES = {"Table_6_Fruit_production": "production_kt",
           "Table_7_Fruit_value_": "value_gbp_m",
           "Table_5_Fruit_yield": "yield_t_ha"}


def _cells(row) -> list[str]:
    out = []
    for c in row.findall(f"{_TBL}table-cell"):
        rep = int(c.get(f"{_TBL}number-columns-repeated", "1"))
        txt = "".join(t.text or "" for t in c.iter(f"{_TXT}p")).strip()
        out += [txt] * min(rep, 40)
    return out


def _num(s: str):
    s = (s or "").replace(",", "")
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def parse(ods: bytes) -> pd.DataFrame:
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(ods)).read("content.xml"))
    series = {}
    for tbl in root.iter(f"{_TBL}table"):
        name = tbl.get(f"{_TBL}name")
        if name not in _TABLES:
            continue
        rows = [_cells(r) for r in tbl.iter(f"{_TBL}table-row")]
        years = next(([(_num(c) if _num(c) and 1990 <= _num(c) <= 2100 else None) for c in r]
                      for r in rows if sum(1 for c in r if _num(c) and 1990 <= (_num(c) or 0) <= 2100) >= 3), None)
        bb = next((r for r in rows if any("blueberr" in (c or "").lower() for c in r)), None)
        if years and bb:
            for i, y in enumerate(years):
                if y and i < len(bb) and _num(bb[i]) is not None:
                    series.setdefault(int(y), {})[_TABLES[name]] = _num(bb[i])
    df = pd.DataFrame([{"year": y, **v} for y, v in sorted(series.items())])
    return df


def refresh(url: str = REPORT_URL) -> pd.DataFrame:
    data = urllib.request.urlopen(urllib.request.Request(url, headers=_HDR), timeout=60).read()
    df = parse(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    return df


def load() -> pd.DataFrame:
    return pd.read_csv(OUT) if OUT.exists() else pd.DataFrame()


if __name__ == "__main__":
    df = refresh()
    print(f"wrote {len(df)} years -> {OUT}")
    print(df.to_string(index=False))
