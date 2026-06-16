"""ONS Shopping Prices retail blueberry price -- year-round historical price.

Unlike DEFRA wholesale (which only quotes blueberries Jun-Nov), the ONS Shopping
Prices Comparison Tool carries a monthly retail blueberry price (GBP/kg) for
EVERY calendar month, Jan 2018 - Jan 2025. That year-round coverage is what makes
it usable in the Dec-May import season, so it is the candidate price signal for
the fusion test.

Caveats kept in view: (1) it is *retail* consumer price (sticky, marked up,
demand-driven), only weakly and contemporaneously related to import volume --
it does not lead; (2) this pre-2025-update download ends Jan 2025 (later months
need the post-update tool, different methodology).
"""
from __future__ import annotations

import datetime as _dt
import io

import pandas as pd
import requests

from .base import SignalSource

_URL = ("https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/"
        "adhocs/2724shoppingpricescomparisontooldatadownloadbeforethe2025update/"
        "datadownload1.xlsx")
_HEADERS = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)"}


class OnsRetailBlueberryPrice(SignalSource):
    series = "ons_blueberry_retail_price"
    freq = "M"
    unit = "gbp_per_kg"

    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        resp = requests.get(_URL, headers=_HEADERS, timeout=60)
        resp.raise_for_status()
        xls = pd.ExcelFile(io.BytesIO(resp.content))

        meta = xls.parse("metadata")
        match = meta[meta["ITEM_DESC"].str.contains("blueberr", case=False, na=False)]
        if match.empty:
            return self._tidy([], vintage_date)
        item_id = match["ITEM_ID"].iloc[0]

        avg = xls.parse("averageprice")
        row = avg[avg["ITEM_ID"] == item_id].drop(columns=["ITEM_ID"]).T.squeeze()
        row.index = pd.to_datetime(row.index)
        row = row.dropna()

        records = [
            {
                "series": self.series,
                "ref_period": d.date().isoformat(),
                "freq": self.freq,
                "key": "",
                "value": float(v),
                "unit": self.unit,
            }
            for d, v in row.items()
        ]
        return self._tidy(records, vintage_date)


if __name__ == "__main__":
    df = OnsRetailBlueberryPrice().fetch()
    print(f"rows: {len(df)}  range: {df['ref_period'].min()}..{df['ref_period'].max()}")
    print(df.tail(5).to_string(index=False))
