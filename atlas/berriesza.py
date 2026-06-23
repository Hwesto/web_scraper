"""Berries ZA -- South Africa weekly blueberry export report (automated PDF parse).

The cleanest committee feed: Berries ZA (ex-SABPA) publishes a weekly Power-BI PDF of
South African blueberry exports by destination region (air/sea/total), season + year-to-
date, with a stable `/download/<id>/` URL. This wires it: find the latest report, parse
the year-to-date-by-region table, write `data/atlas/sa_exports.csv`. Genuinely current --
the runner re-parses each week (unlike the hand-curated campaign snapshots).

Numbers are European-formatted (space thousands, comma decimal: "10 917,37" -> 10917.37).
Best-effort: a failed fetch/parse leaves the committed snapshot. Chile's committee report
is chart-only (not text-parseable) and Argentina's latest file is a stale headerless grid,
so South Africa is the one automatable committee PDF -- the rest stay snapshots.
"""
from __future__ import annotations

import io
import re
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "sa_exports.csv"
REPORTS = "https://berriesza.co.za/export-reports/"
_REGIONS = ["Africa", "Europe", "Far East & Asia", "Indian Ocean Islands", "Middle East",
            "Other", "Russian Federation", "United Kingdom", "USA & Canada", "Total"]
_NUM = re.compile(r"\d{1,3}(?: \d{3})*(?:,\d+)?")
_COLS = ["region", "air_t", "sea_t", "total_t", "season", "week", "source"]


def _eu(tok: str) -> float:
    return float(re.sub(r"\s", "", tok).replace(",", "."))


def _parse(text: str) -> pd.DataFrame:
    """Parse the 'Year To Date' region table (offline-testable) -> 25/26 air/sea/total."""
    # PDF uses non-breaking/thin spaces as the thousands separator -> ASCII space
    text = "".join(" " if (c.isspace() and c != chr(10)) else c for c in text)
    sm = re.search(r"Season\s+(\d{4}/\d{4})\s*-\s*Week\s+(\d+)", text)
    season = sm.group(1) if sm else ""
    week = int(sm.group(2)) if sm else 0
    i = text.find("Year To Date")
    block = text[i:i + 1200] if i >= 0 else ""
    rows = []
    for line in block.splitlines():
        s = line.strip()
        region = next((r for r in _REGIONS if s.startswith(r)), None)
        if not region:
            continue
        nums = _NUM.findall(s[len(region):])
        if len(nums) < 3:
            continue
        rows.append({"region": region, "air_t": _eu(nums[0]), "sea_t": _eu(nums[1]),
                     "total_t": _eu(nums[2]), "season": season, "week": week,
                     "source": "Berries ZA"})
    return pd.DataFrame(rows, columns=_COLS)


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    return urllib.request.urlopen(req, timeout=45).read()


def _latest_pdf_url() -> str | None:
    html = _fetch(REPORTS).decode("utf-8", "replace")
    for url, title in re.findall(r'href="(https://[^"]*?/download/\d+/[^"]*)"[^>]*>([^<]{0,70})', html):
        if "Exports from South Africa" in title:
            return url
    return None


def refresh() -> pd.DataFrame:
    url = _latest_pdf_url()
    if not url:
        raise RuntimeError("Berries ZA: no export report link found")
    from pypdf import PdfReader
    txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(_fetch(url))).pages)
    df = _parse(txt)
    if not df.empty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE, index=False)
    return df


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def headline() -> str | None:
    df = load()
    if df.empty:
        return None
    tot = df[df["region"] == "Total"]
    if tot.empty:
        return None
    r = tot.iloc[0]
    return f"{r['season']} to wk{int(r['week'])}: {r['total_t']/1000:.1f}kt"


if __name__ == "__main__":
    df = refresh()
    print(headline())
    print(df.to_string(index=False))
