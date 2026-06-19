"""USD→GBP reference rate — replaces the notional 0.79 used in netback/wedge/FOB.

Free, no-key, ECB-backed (Frankfurter). The weekly cron refreshes a committed cache;
the stack reads it offline and falls back to the notional if the cache is absent, so
nothing breaks without the network.
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import urllib.request

from nowcast.config import DATA_DIR

CACHE = DATA_DIR / "market" / "fx_usd_gbp.csv"
_URL = "https://api.frankfurter.app/latest?from=USD&to=GBP"
_HEADERS = {"User-Agent": "uk-blueberry-nowcast/0.1", "Accept": "application/json"}
_NOTIONAL = 0.79                      # documented fallback (the old hard-coded rate)


def refresh() -> float:
    """Fetch the latest GBP-per-USD rate and append it to the committed cache."""
    d = json.load(urllib.request.urlopen(
        urllib.request.Request(_URL, headers=_HEADERS), timeout=30))
    date, rate = d["date"], float(d["rates"]["GBP"])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    rows = {}
    if CACHE.exists():
        with CACHE.open() as fh:
            rows = {r["date"]: r["gbp_per_usd"] for r in csv.DictReader(fh)}
    rows[date] = f"{rate:.5f}"
    with CACHE.open("w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "gbp_per_usd"])
        for dt in sorted(rows):
            w.writerow([dt, rows[dt]])
    return rate


def gbp_per_usd() -> float:
    """Latest cached GBP-per-USD; falls back to the documented notional if no cache."""
    if not CACHE.exists():
        return _NOTIONAL
    with CACHE.open() as fh:
        rows = list(csv.DictReader(fh))
    return float(rows[-1]["gbp_per_usd"]) if rows else _NOTIONAL


if __name__ == "__main__":
    print(f"refreshed GBP per USD = {refresh():.5f} -> {CACHE}")
