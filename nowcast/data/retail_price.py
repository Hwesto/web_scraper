"""Live retail blueberry price scraper -- forward-collection price signal.

Why this exists: the ONS Shopping Prices history (ons_price.py) is a clean,
year-round retail blueberry price but ENDS Jan 2025. To keep a year-round price
flowing past that, we scrape current supermarket prices and stamp them daily.

Status / honesty:
  - Like the packhouse-hiring collector, this has NO history before today, so it
    cannot contribute to the historical backtest -- it only accrues forward.
  - The fusion test already showed (on the year-round ONS history) that retail
    price barely correlates with import volume and does not lead it, so this is
    a low-expectation signal kept alive mainly to confirm/deny that forward.
  - Supermarket sites are JS-heavy and bot-protected; a robust live scrape needs
    per-retailer handling. This is a deliberate stub fixing the schema and the
    target list; the per-site extraction is a TODO once a real need is signed off.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

from .base import SignalSource

# (retailer, product search/landing URL) -- blueberry punnet listings.
RETAILER_TARGETS = [
    ("tesco", "https://www.tesco.com/groceries/en-GB/search?query=blueberries"),
    ("sainsburys", "https://www.sainsburys.co.uk/gol-ui/SearchResults/blueberries"),
    ("ocado", "https://www.ocado.com/search?entry=blueberries"),
]


class RetailBlueberryPrice(SignalSource):
    series = "retail_blueberry_price"
    freq = "W"
    unit = "gbp_per_kg"

    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        # TODO: per-retailer extraction of punnet price + pack size -> GBP/kg,
        # median across retailers per week. Until then emit an empty tidy frame
        # so the pipeline runs and the contract is fixed (forward-collection).
        records: list[dict] = []
        return self._tidy(records, vintage_date)


if __name__ == "__main__":
    df = RetailBlueberryPrice().fetch()
    print(f"retail_blueberry_price rows: {len(df)} (stub -- forward collection)")
