"""UK domestic fruit production from DEFRA Horticulture Statistics (annual).

The British-season supply Britain grows itself — production (kt), value (£m) and
yield (t/ha) by year, per fruit. Each fruit names the DEFRA Table-6/7/5 row(s) it
sums (e.g. apple = Dessert + Culinary) via `Fruit.defra_rows`; soft-fruit varieties
sit in the table's column B ("Strawberries"), orchard totals in column B too
("Total Pears :"). Area is suppressed by DEFRA (too few growers). Annual ODS on
gov.uk; parsed via zipfile (no odfpy dep). Manual refresh: bump REPORT_URL yearly.

Per-fruit cache: data/market/uk_<slug>_production.csv. A fruit whose row is blank in
the current report (DEFRA suppresses blueberry detail in 2024) keeps its last good
cache — refresh() never overwrites real data with an all-blank pull.
"""
from __future__ import annotations

import io
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from deep.config import DATA_DIR

REPORT_URL = ("https://assets.publishing.service.gov.uk/media/685ba429e9509f1a908eb16b/"
              "hort-dataset-24-20250626.ods")
_HDR = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)"}
_TBL = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_TXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_TABLES = {"Table_6_Fruit_production": "production_kt",
           "Table_7_Fruit_value_": "value_gbp_m",
           "Table_5_Fruit_yield": "yield_t_ha"}


def _out(slug: str):
    return DATA_DIR / "market" / f"uk_{slug}_production.csv"


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


def _label(cells: list[str]) -> str:
    """The row's fruit label — DEFRA puts the variety/total in column B (cells[1]),
    falling back to column A for orchard parents."""
    return (cells[1].strip() if len(cells) > 1 and cells[1].strip()
            else (cells[0].strip() if cells else ""))


def parse(ods: bytes, rows_match: tuple[str, ...]) -> pd.DataFrame:
    """Sum the production/value/yield of the DEFRA rows whose label contains any of
    `rows_match`, by year. Multi-row fruits (apple) sum production & value; yield is
    only meaningful for a single row, so it is left out when ≥2 rows match."""
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(ods)).read("content.xml"))
    matchers = tuple(m.lower() for m in rows_match)
    series: dict[int, dict] = {}
    for tbl in root.iter(f"{_TBL}table"):
        name = tbl.get(f"{_TBL}name")
        if name not in _TABLES:
            continue
        metric = _TABLES[name]
        rows = [_cells(r) for r in tbl.iter(f"{_TBL}table-row")]
        years = next(([(_num(c) if _num(c) and 1990 <= _num(c) <= 2100 else None) for c in r]
                      for r in rows if sum(1 for c in r if _num(c) and 1990 <= (_num(c) or 0) <= 2100) >= 3), None)
        if not years:
            continue
        matched = [r for r in rows if any(m in _label(r).lower() for m in matchers)]
        single = len(matched) == 1
        for r in matched:
            if metric == "yield_t_ha" and not single:    # can't sum yields
                continue
            for i, y in enumerate(years):
                if y and i < len(r) and _num(r[i]) is not None:
                    cell = series.setdefault(int(y), {})
                    cell[metric] = cell.get(metric, 0.0) + _num(r[i])
    df = pd.DataFrame([{"year": y, **v} for y, v in sorted(series.items())])
    return df


def refresh(slug: str, rows_match: tuple[str, ...], url: str = REPORT_URL) -> pd.DataFrame:
    data = urllib.request.urlopen(urllib.request.Request(url, headers=_HDR), timeout=90).read()
    df = parse(data, rows_match)
    out = _out(slug)
    # Don't clobber a good cache with an all-blank pull (DEFRA blanks blueberry in 2024).
    if df.empty or "production_kt" not in df or df["production_kt"].dropna().empty:
        return load(slug)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df


def load(slug: str = "blueberry") -> pd.DataFrame:
    out = _out(slug)
    return pd.read_csv(out) if out.exists() else pd.DataFrame()


if __name__ == "__main__":
    import sys
    from core.fruit import FRUITS
    # Default skips blueberry: it keeps its curated cache (DEFRA's 2024 report
    # suppresses the blueberry detail). Pass it explicitly to force a re-pull.
    targets = [FRUITS[a] for a in sys.argv[1:]] if sys.argv[1:] else \
              [f for f in FRUITS.values() if f.defra_production and f.slug != "blueberry"]
    for fr in targets:
        df = refresh(fr.slug, fr.defra_rows)
        latest = df.iloc[-1].to_dict() if not df.empty else {}
        print(f"{fr.slug:12s} {len(df)} yrs -> {_out(fr.slug).name}  latest={latest}")
