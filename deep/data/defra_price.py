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
from bs4 import BeautifulSoup

from .base import SignalSource
from ..config import DEFRA_PRICE_PAGE

_HEADERS = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)"}


def _discover_csv_url() -> str:
    """Find the current machine-readable CSV link on the DEFRA dataset page."""
    resp = requests.get(DEFRA_PRICE_PAGE, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if href.lower().endswith(".csv"):
            return href
    raise RuntimeError("No CSV link found on DEFRA price page")


class DefraBlueberryPrice(SignalSource):
    """Wholesale blueberry price (GBP/kg) from DEFRA, at its native cadence."""

    series = "defra_blueberry_price"
    freq = "W"            # nominal; real cadence is weekly->fortnightly, gaps in winter
    unit = "gbp_per_kg"

    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        csv_url = _discover_csv_url()
        resp = requests.get(csv_url, headers=_HEADERS, timeout=40)
        resp.raise_for_status()

        frame = pd.read_csv(io.StringIO(resp.text))
        blue = frame[frame["item"].str.contains("blueberr", case=False, na=False)].copy()

        records = [
            {
                "series": self.series,
                "ref_period": pd.to_datetime(row["date"]).date().isoformat(),
                "freq": self.freq,
                "key": "",
                "value": float(row["price"]),
                "unit": self.unit,
            }
            for _, row in blue.iterrows()
        ]
        return self._tidy(records, vintage_date)


if __name__ == "__main__":
    df = DefraBlueberryPrice().fetch()
    print(f"rows: {len(df)}")
    print(f"period range: {df['ref_period'].min()} .. {df['ref_period'].max()}")
    print(df.sort_values("ref_period").tail(8).to_string(index=False))
