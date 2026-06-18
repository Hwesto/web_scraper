"""Fetch the SAG roster of Chilean blueberry orchards authorised to export to China.

SAG publishes the season list two ways: a Power BI report (hard to scrape) and an
Excel on its own site -- "<season> BLUEBERRY-records-for-CHINA <date> web.xlsx".
We take the Excel: it is the authoritative, stable, structured source. The file is
reachable from clean egress but blocked from the Claude sandbox, so -- like the
datos.gob.cl weekly feed -- this runs on a GitHub runner and IS the access method.

Robust to the seasonal re-publish: it scrapes the SAG registros listing for the
current blueberry/China .xlsx link rather than hardcoding the dated filename, then
parses the "Orchard" sheet (header row detected, not assumed) into
data/market/sag_china_orchards.csv.

  python scripts/fetch_sag_china.py            # discover + download + parse
  python scripts/fetch_sag_china.py --url URL  # parse a specific xlsx (or local path)
"""
from __future__ import annotations

import argparse
import io
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "market" / "sag_china_orchards.csv"
LISTING = "https://www.sag.gob.cl/ambitos-de-accion/exportaciones/registros?title=blueberry+china"
HOST = "https://www.sag.gob.cl"
_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/vnd.openxmlformats-"
              "officedocument.spreadsheetml.sheet,*/*",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Referer": HOST + "/",
}
# columns we keep, mapped from the (bilingual) SAG headers
_WANT = {"ORCHARD CODE (CSG)": "csg_code", "GROWER NAME": "grower_name",
         "ORCHARD NAME": "orchard_name", "COD. REGIÓN": "cod_region",
         "REGION": "region", "DISTRICT": "district"}


def _get(url: str, retries: int = 5) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=_HDR), timeout=90) as r:
                return r.read()
        except Exception as e:                          # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{url} failed: {last}")


def discover_xlsx() -> str:
    """Find the current blueberry-to-China .xlsx link on the SAG registros page."""
    html = _get(LISTING).decode("utf-8", "ignore")
    hrefs = re.findall(r'href="([^"]+\.xlsx)"', html, flags=re.I)
    for h in hrefs:
        if re.search(r"blueberry|arandan", h, re.I) and re.search(r"china", h, re.I):
            return h if h.startswith("http") else HOST + h
    raise RuntimeError(f"no blueberry/China xlsx link found ({len(hrefs)} xlsx links seen)")


def _detect_header(raw: pd.DataFrame) -> int:
    for i in range(min(15, len(raw))):
        row = raw.iloc[i].astype(str).str.upper().str.cat(sep=" ")
        if "GROWER NAME" in row and "CSG" in row:
            return i
    raise RuntimeError("could not locate the header row (GROWER NAME / CSG)")


def parse_xlsx(data: bytes | str | Path) -> pd.DataFrame:
    src = io.BytesIO(data) if isinstance(data, bytes) else data
    xl = pd.ExcelFile(src)
    sheet = next((s for s in xl.sheet_names if "orchard" in s.lower()
                  or "果园" in s), xl.sheet_names[0])
    raw = xl.parse(sheet, header=None)
    hdr = _detect_header(raw)
    df = xl.parse(sheet, header=hdr)
    df.columns = [str(c).split("\n")[0].strip() for c in df.columns]
    cols = {c: _WANT[c] for c in df.columns if c in _WANT}
    df = df.rename(columns=cols)[list(cols.values())]
    df = df[df["grower_name"].notna() & df["csg_code"].notna()].copy()
    df["grower_name"] = df["grower_name"].astype(str).str.strip()
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="specific .xlsx URL or local path (else auto-discover)")
    args = ap.parse_args()

    if args.url and Path(args.url).exists():
        df = parse_xlsx(Path(args.url))
        src = args.url
    else:
        src = args.url or discover_xlsx()
        print(f"source: {src}")
        df = parse_xlsx(_get(src))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"wrote {len(df)} orchards ({df['grower_name'].nunique()} growers) -> {OUT}")


if __name__ == "__main__":
    main()
