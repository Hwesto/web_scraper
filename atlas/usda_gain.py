"""Forward-looking production/trade forecasts from USDA-FAS GAIN blueberry reports.

The forecast axis -- the one measurement only an analyst, not Comtrade or FAOSTAT,
provides. USDA-FAS posts publish a "Blueberry Annual" per major country with
season-ahead production / export / import forecasts. Peru's is already wired
structurally (`scripts/fetch_usda_peru.py` -> the full PSD table); this adds the
other posts (Mexico, China) by extracting the headline forecast figures from the
report narrative -- which is far more consistent across reports than the per-report
PSD table layout (verified 2026-06).

Snapshot-style + fragile by nature: the GAIN download filename changes each cycle
(no free search API; fas.usda.gov 403s bots), so REPORTS is hand-pinned and must be
bumped when a new annual publishes -- same contract as the Peru fetcher. Best-effort:
a post that fails to download/parse is skipped, not fatal. Committed to
`data/atlas/usda_forecasts.csv`.
"""
from __future__ import annotations

import io
import re
import urllib.parse
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "usda_forecasts.csv"
_BASE = "https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName="
# country -> GAIN report filename (hand-pinned; bump when a new annual publishes).
REPORTS = {
    "Peru": "Blueberry Annual_Lima_Peru_PE2025-0010.pdf",
    "Mexico": "Blueberry Annual Voluntary _Guadalajara_Mexico_MX2025-0004",
    # China's latest Blueberry Annual (CH2023-0046) is qualitative -- no MT forecast
    # figures to extract -- so it's catalogued (registry) but not pinned here.
}
_COLS = ["country", "metric", "year", "value_mt", "source"]
# metric keyword -> normalized label
_METRIC = re.compile(r"(production|exports?|imports?)\b[^.]{0,60}?"
                     r"\b(\d{1,3}(?:,\d{3})+)\s*(?:metric tons|MT)\b", re.I)
_YEAR = re.compile(r"(?:CY|MY|calendar year(?:\s*\(CY\))?)\s*(20\d{2})", re.I)


def _extract(text: str, country: str) -> pd.DataFrame:
    """Pull headline forecast figures (production/exports/imports, MT, year) from the
    report narrative (offline-testable). Keeps forecast sentences, one row per
    (metric, year)."""
    flat = re.sub(r"\s+", " ", text)
    rows: dict[tuple, dict] = {}
    for sent in re.split(r"(?<=[.])\s", flat):
        if "forecast" not in sent.lower():
            continue
        ym = _YEAR.search(sent) or re.search(r"\b(20\d{2})\b", sent)
        if not ym:
            continue
        year = int(ym.group(1))
        for m in _METRIC.finditer(sent):
            metric = m.group(1).lower().rstrip("s")        # export/import/production
            metric = {"export": "exports", "import": "imports"}.get(metric, metric)
            value = int(m.group(2).replace(",", ""))
            rows.setdefault((metric, year), {
                "country": country, "metric": metric, "year": year,
                "value_mt": value, "source": f"USDA-FAS GAIN ({country})"})
    return pd.DataFrame(rows.values(), columns=_COLS)


def _download(filename: str, retries: int = 4) -> bytes:
    import time
    url = _BASE + urllib.parse.quote_plus(filename)        # API form-encodes spaces as '+'
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            return urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:                             # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GAIN download failed ({filename[:40]}...): {last}")


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)


def refresh(reports: dict[str, str] | None = None) -> pd.DataFrame:
    """Fetch + extract each country's GAIN forecast; (re)write the cache. Best-effort
    per country (a failed post is skipped, not fatal)."""
    reports = reports or REPORTS
    parts = []
    for country, filename in reports.items():
        try:
            df = _extract(_pdf_text(_download(filename)), country)
            if not df.empty:
                parts.append(df)
        except Exception as e:                             # noqa: BLE001
            print(f"skip {country}: {type(e).__name__} {str(e)[:70]}")
    fresh = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=_COLS)
    if not fresh.empty:
        fresh = fresh.sort_values(["country", "metric", "year"]).reset_index(drop=True)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


if __name__ == "__main__":                                 # python -m atlas.usda_gain
    df = refresh()
    print(f"cached {len(df)} forecast figures -> {CACHE}")
    print(df.to_string(index=False))
