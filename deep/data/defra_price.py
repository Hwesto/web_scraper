"""DEFRA weekly wholesale price ingest -- price/anomaly proxy (demand-confounded).

Pulls the machine-readable wholesale price CSV from gov.uk and extracts the
blueberry line (GBP/kg).

Two real limitations, surfaced not hidden:
  1. Cadence moved weekly -> fortnightly in Dec 2024.
  2. DEFRA only quotes blueberries while UK home-grown is in season (~Jun-Nov);
     it is largely SILENT Dec-May -- which is exactly the Spain/Morocco import
     window we target. So this signal is anti-aligned with the target season and
     is treated as an off-season/price-context input, not the in-season driver.
     (The in-season weekly driver is intended to be retail-price scraping.)

The CSV filename is date-stamped, so we discover the current link from the page
rather than hard-coding it.
"""
from __future__ import annotations

import datetime as _dt
import io

import pandas as pd
import requests

from .base import SignalSource
from ..config import DEFRA_PRICE_PAGE

_HEADERS = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)"}


def _discover_csv_url() -> str:
    """Find the current machine-readable CSV link on the DEFRA dataset page."""
    from bs4 import BeautifulSoup  # lazy: an optional scraper dep must not break module import
    resp = requests.get(DEFRA_PRICE_PAGE, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if href.lower().endswith(".csv"):
            return href
    raise RuntimeError("No CSV link found on DEFRA price page")


# DEFRA wholesale CSV item names per atlas fruit — UK-grown, British-season £/kg
# (New Covent Garden). A different product from the imported mainstream: for premium
# British soft fruit it can sit near/above retail, for top/stone fruit it's a clean
# mid-point; either way the board shows it as a parallel reference, not a journey step.
DEFRA_ITEMS = {
    "blueberry": "blueberries", "apple": "apples", "pear": "pears", "plum": "plums",
    "cherry": "cherries", "strawberry": "strawberries", "raspberry": "raspberries",
}


class DefraPrice(SignalSource):
    """Wholesale UK £/kg for one fruit from the DEFRA weekly CSV — the British-season
    home-grown spot price. Multiple varieties (apples) are averaged to one price per
    date; non-kg units are dropped. Series `defra_<slug>_price`."""

    freq = "W"            # nominal; real cadence is weekly->fortnightly, gaps in winter
    unit = "gbp_per_kg"

    def __init__(self, slug: str = "blueberry", item: str | None = None):
        self.slug = slug
        self.series = f"defra_{slug}_price"
        self.item = item or DEFRA_ITEMS.get(slug, slug)

    def fetch(self, vintage_date: _dt.date | None = None,
              frame: "pd.DataFrame | None" = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        if frame is None:
            resp = requests.get(_discover_csv_url(), headers=_HEADERS, timeout=40)
            resp.raise_for_status()
            frame = pd.read_csv(io.StringIO(resp.text))
        sub = frame[(frame["item"] == self.item) & (frame.get("unit", "kg") == "kg")].copy()
        if sub.empty:
            return self._tidy([], vintage_date)
        sub["d"] = pd.to_datetime(sub["date"])
        by_date = sub.groupby("d")["price"].mean()      # mean across varieties → one £/kg/date
        records = [
            {"series": self.series, "ref_period": d.date().isoformat(), "freq": self.freq,
             "key": "", "value": float(p), "unit": self.unit}
            for d, p in by_date.items()
        ]
        return self._tidy(records, vintage_date)


class DefraBlueberryPrice(DefraPrice):
    """Back-compat shim for the pipeline/tests — the original blueberry source."""

    def __init__(self):
        super().__init__("blueberry")


def refresh_all(slugs=tuple(DEFRA_ITEMS)):
    """Download the DEFRA CSV ONCE and write each fruit's wholesale £/kg to the vintage
    store. Returns {slug: n_rows}."""
    from ..store import vintage
    resp = requests.get(_discover_csv_url(), headers=_HEADERS, timeout=40)
    resp.raise_for_status()
    frame = pd.read_csv(io.StringIO(resp.text))
    out = {}
    for slug in slugs:
        df = DefraPrice(slug).fetch(frame=frame)
        if not df.empty:
            vintage.save(df)
        out[slug] = len(df)
    return out


if __name__ == "__main__":
    import sys
    slugs = sys.argv[1:] or list(DEFRA_ITEMS)
    for slug, n in refresh_all(slugs).items():
        print(f"defra_{slug}_price: {n} rows")
