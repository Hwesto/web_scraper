"""ONS retail blueberry price -- year-round, now extended past the 2025 break.

History: the ONS Shopping Prices tool carried a monthly item-level *blueberry*
price (GBP/kg) Jan 2018 - Jan 2025. The March-2025 methodology update dropped
item-level blueberries and replaced them with a broader consumption segment,
"Berries, fresh" (CP0116401), which is published only as a chained price INDEX
(Jan 2025 = 100) -- no absolute GBP/kg, and no longer blueberry-specific.

So a clean blueberry GBP/kg simply does not exist after Jan 2025. To keep a
year-round price flowing across the Dec-May import window (the whole point of
using ONS over the Jun-Nov-only DEFRA wholesale), we SPLICE:

  * direct blueberry GBP/kg through Jan 2025                         key=""
  * Jan-2025 blueberry level carried forward by the all-fresh-berries
    price index thereafter -- a documented PROXY, not a measurement  key="proxy_berries_index"

The two series share exactly one month (Jan 2025), which is the splice anchor.
The proxy assumes blueberry retail tracks the fresh-berry category; honest
limitation, surfaced in `key` so downstream can include/exclude it. If the new
feed is unreachable the source degrades to the direct-only series rather than
faking anything. Caveat unchanged: retail price is sticky/demand-driven and does
not lead import volume -- it is an economics/context signal, not the driver.
"""
from __future__ import annotations

import datetime as _dt
import io

import pandas as pd
import requests

from .base import SignalSource

# pre-2025-update tool: item-level blueberry GBP/kg, Jan 2018 - Jan 2025
_URL_OLD = ("https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/"
            "adhocs/2724shoppingpricescomparisontooldatadownloadbeforethe2025update/"
            "datadownload1.xlsx")
# post-2025 tool's "download all data" (the live file the tool itself loads)
_URL_NEW = "https://github.com/onsdigital/cpi-items-actions/raw/main/datadownload.xlsx"
_BERRIES_SEGMENT = "CP0116401"          # "Berries, fresh" consumption segment
_HEADERS = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)"}


def _series_from_sheet(xls: pd.ExcelFile, sheet: str, item_id) -> pd.Series:
    df = xls.parse(sheet)
    row = df[df["ITEM_ID"] == item_id]
    if row.empty:
        return pd.Series(dtype=float)
    s = row.drop(columns=["ITEM_ID"]).T.squeeze("columns")
    s.index = pd.to_datetime(s.index)
    return s.dropna().astype(float)


def _blueberry_gbp_per_kg(xls: pd.ExcelFile) -> pd.Series:
    meta = xls.parse("metadata")
    match = meta[meta["ITEM_DESC"].str.contains("blueberr", case=False, na=False)]
    if match.empty:
        return pd.Series(dtype=float)
    return _series_from_sheet(xls, "averageprice", match["ITEM_ID"].iloc[0])


class OnsRetailBlueberryPrice(SignalSource):
    series = "ons_blueberry_retail_price"
    freq = "M"
    unit = "gbp_per_kg"

    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()

        old_xls = pd.ExcelFile(io.BytesIO(self._get(_URL_OLD)))
        direct = _blueberry_gbp_per_kg(old_xls)
        if direct.empty:
            return self._tidy([], vintage_date)

        proxy = self._proxy_extension(direct)

        records = [self._row(d, v, "") for d, v in direct.items()]
        records += [self._row(d, v, "proxy_berries_index") for d, v in proxy.items()]
        return self._tidy(records, vintage_date)

    # -- helpers --
    def _proxy_extension(self, direct: pd.Series) -> pd.Series:
        """All-berries index, rescaled to the blueberry level at the shared month."""
        try:
            new_xls = pd.ExcelFile(io.BytesIO(self._get(_URL_NEW)))
            idx = _series_from_sheet(new_xls, "chained", _BERRIES_SEGMENT)
        except Exception:                               # noqa: BLE001 -- degrade, don't fake
            return pd.Series(dtype=float)
        anchor_dates = direct.index.intersection(idx.index)
        if anchor_dates.empty:
            return pd.Series(dtype=float)
        anchor = anchor_dates.max()
        scaled = direct.loc[anchor] * idx / idx.loc[anchor]
        return scaled[scaled.index > anchor]            # only months beyond direct coverage

    def _row(self, d, v, key: str) -> dict:
        return {"series": self.series, "ref_period": d.date().isoformat(),
                "freq": self.freq, "key": key, "value": float(v), "unit": self.unit}

    @staticmethod
    def _get(url: str) -> bytes:
        resp = requests.get(url, headers=_HEADERS, timeout=90)
        resp.raise_for_status()
        return resp.content


if __name__ == "__main__":
    df = OnsRetailBlueberryPrice().fetch()
    direct = df[df["key"] == ""]
    proxy = df[df["key"] == "proxy_berries_index"]
    print(f"rows: {len(df)}  range: {df['ref_period'].min()}..{df['ref_period'].max()}")
    print(f"  direct blueberry: {len(direct)} (..{direct['ref_period'].max() if len(direct) else '-'})")
    print(f"  proxy extension:  {len(proxy)} ({proxy['ref_period'].min() if len(proxy) else '-'}..)")
    print(df.tail(6).to_string(index=False))
