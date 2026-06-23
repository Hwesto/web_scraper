"""USDA-AMS weekly US blueberry movement by origin (report WA_FV408).

The unique view no other free source gives: weekly + season-to-date SHIPMENTS into the US
market by ORIGIN -- both US domestic states (Georgia, Michigan, Oregon...) and import
origins (Peru, Chile, Mexico, Canada...). Comtrade has the Peru->US bilateral lane but
nothing on US domestic supply or this weekly granularity.

Source: USDA-AMS Specialty Crops Market News, keyless mirror
`ams.usda.gov/mnreports/wa_fv408.txt` (units of 10,000 lb). Honesty: the keyless mirror /
ESMIS releases run to ~early-2025 (the report looks discontinued keylessly); the LIVE
weekly feed is the MyMarketNews MARS API (slug 3251) which needs a free API key -- set
AMS_API_KEY to switch to it. Best-effort: a failed fetch leaves the committed snapshot.
"""
from __future__ import annotations

import datetime as _dt
import re
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "usda_movement.csv"
TXT_URL = "https://www.ams.usda.gov/mnreports/wa_fv408.txt"
_LB_UNIT_T = 10000 * 0.453592 / 1000   # 1 report unit = 10,000 lb -> 4.53592 tonnes
_COLS = ["origin", "kind", "week_t", "season_t", "report_date", "source"]
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
_ROW = re.compile(r"^\s+([A-Z][A-Z .-]+?)\s+((?:[-\d,]+\s+){5}[-\d,]+)\s*$")
_SKIP = {"TOTAL", "U.S. TOTAL", "IMPORT TOTAL", "COMMODITY TOTAL"}


def _num(tok: str):
    return 0.0 if tok.strip() in ("-", "") else float(tok.replace(",", ""))


def _parse(text: str) -> pd.DataFrame:
    """Parse the conventional BLUEBERRIES table (offline-testable): per origin the latest
    week (col 1) and the season-to-date (col 4), as domestic vs import, in tonnes."""
    lines = text.splitlines()
    dm = re.search(r"\b([A-Z]{3})\s+(\d{1,2})\s+(20\d\d)", text)
    report_date = ""
    if dm and dm.group(1) in _MONTHS:
        report_date = f"{int(dm.group(3))}-{_MONTHS[dm.group(1)]:02d}-{int(dm.group(2)):02d}"
    # the conventional block: from a line that is exactly BLUEBERRIES to ORGANIC/COMMODITY TOTAL
    start = next((i for i, l in enumerate(lines) if l.strip() == "BLUEBERRIES"), None)
    if start is None:
        return pd.DataFrame(columns=_COLS)
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip().startswith(("BLUEBERRIES - ORGANIC", "COMMODITY TOTAL"))), len(lines))
    rows, kind = [], "domestic"
    for l in lines[start:end]:
        s = l.strip()
        if s == "IMPORT":
            kind = "import"; continue
        m = _ROW.match(l)
        if not m or m.group(1).strip() in _SKIP:
            continue
        nums = m.group(2).split()
        if len(nums) != 6:
            continue
        origin = m.group(1).strip().title()
        rows.append({"origin": origin, "kind": kind,
                     "week_t": round(_num(nums[0]) * _LB_UNIT_T, 1),
                     "season_t": round(_num(nums[3]) * _LB_UNIT_T, 1),
                     "report_date": report_date, "source": "USDA-AMS WA_FV408"})
    return pd.DataFrame(rows, columns=_COLS)


def _download(url: str = TXT_URL, retries: int = 4) -> str:
    import time
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
        except Exception as e:                             # noqa: BLE001
            last = e; time.sleep(2 ** attempt)
    raise RuntimeError(f"AMS movement fetch failed: {last}")


def refresh(url: str = TXT_URL) -> pd.DataFrame:
    df = _parse(_download(url))
    if not df.empty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.sort_values(["kind", "season_t"], ascending=[True, False]).to_csv(CACHE, index=False)
    return df


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


if __name__ == "__main__":
    df = refresh()
    rd = df["report_date"].iloc[0] if len(df) else "-"
    print(f"US blueberry supply by origin (WA_FV408, season-to-date as of {rd}):")
    print(df.to_string(index=False))
