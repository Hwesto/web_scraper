"""Peru blueberry fundamentals from the USDA-FAS 'Blueberry Annual' (Lima).

Peru has no per-block orchard census (no Chile-style Catastro), so this authoritative
annual report is the structural + forward layer instead: harvested area, production,
exports, exports-to-US, with FAS estimates/forecasts two seasons out. Parses the PSD
table (Table 1) into data/market/peru_fundamentals.csv.

Annual report; the filename changes each year (PEYYYY-NNNN) -- update REPORT_URL when
the new one lands. Reads a local PDF if given, else downloads. USDA FAS is reachable
from clean egress; run on the runner if the sandbox blocks it.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from deep.config import DATA_DIR

OUT = DATA_DIR / "market" / "peru_fundamentals.csv"
REPORT_URL = ("https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName"
              "?fileName=Blueberry+Annual_Lima_Peru_PE2025-0010.pdf")
_HEADERS = {"User-Agent": "Mozilla/5.0 (uk-blueberry-nowcast research)"}
# PSD rows we keep -> output column
_ROWS = {
    "Area Harvested": "area_ha",
    "Production (": "production_mt",
    "Exports (": "exports_mt",
    "Exports to the U.S.": "exports_us_mt",
}


def _nums(line: str) -> list[int]:
    """Integer values on a PSD row, dropping any 'NN%' change column."""
    line = re.sub(r"\d+\s*%", " ", line)             # strip the % change col
    return [int(t.replace(",", "")) for t in re.findall(r"\b\d[\d,]{2,}\b", line)]


def parse(pdf_bytes: bytes) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        txt = "\n".join((p.extract_text() or "") for p in pdf.pages)
    # seasons from the PSD Table-1 header ("Blueberry, Fresh <years>"), in column
    # order -- other tables in the report carry different year spans
    header = next((l for l in txt.splitlines()
                   if "Blueberry, Fresh" in l and re.search(r"20\d{2}/\d{2}", l)), "")
    seasons = re.findall(r"20\d{2}/\d{2}", header)
    if len(seasons) < 4:
        raise RuntimeError(f"could not find PSD header seasons (got {seasons})")
    data = {}
    for line in txt.splitlines():
        for label, col in _ROWS.items():
            if line.strip().startswith(label):
                vals = _nums(line)[:len(seasons)]
                if len(vals) == len(seasons):
                    data[col] = vals
    if "exports_mt" not in data:
        raise RuntimeError("PSD export row not found")
    df = pd.DataFrame(data)
    df.insert(0, "season", seasons)
    # last two seasons are FAS forecasts, the prior one an estimate, rest actual
    status = ["actual"] * (len(seasons) - 3) + ["estimate", "forecast", "forecast"]
    df["status"] = status[-len(seasons):]
    df["exports_us_share_%"] = (df["exports_us_mt"] / df["exports_mt"] * 100).round(1)
    df["source"] = "USDA-FAS Blueberry Annual (Lima)"
    return df


def refresh(url: str = REPORT_URL, local: str | None = None) -> pd.DataFrame:
    if local:
        data = open(local, "rb").read()
    else:
        data = urllib.request.urlopen(
            urllib.request.Request(url, headers=_HEADERS), timeout=60).read()
    df = parse(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    return df


def load() -> pd.DataFrame:
    return pd.read_csv(OUT) if OUT.exists() else pd.DataFrame()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="parse a local PDF instead of downloading")
    df = refresh(local=ap.parse_args().local)
    print(f"wrote {len(df)} seasons -> {OUT}")
    print(df.to_string(index=False))
