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
    price index thereafter -- a documented PROXY, not a measurement  key="proxy_<segment>"

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


# Per-fruit ONS retail price: (old item_id with the averageprice series, new
# consumption segment for the post-2025 index extension, standard whole-fruit weight
# in grams or None). ONS quotes some items "per kg" (weight=None — use directly) and
# others "each" (weight set — divide by it to get an ESTIMATED £/kg). The standard
# weights are a sourced unit conversion, not a measurement: USDA FoodData Central
# 1-medium-fruit weights (melon/pineapple = typical whole retail), surfaced on the
# board as an estimate with the weight stated.
ONS_ITEMS = {
    "blueberry": (212733, _BERRIES_SEGMENT, None),   # per kg — keeps the original series
    "banana":    (212719, "CP0116101", None),        # per kg
    "mandarin":  (212725, "CP0116201", None),        # per kg
    # --- "each"-priced items: £/kg estimated via a standard whole-fruit weight ---
    "apple":     (212735, "CP0116301", 180),         # Apples, fresh (whole medium)
    "orange":    (212709, "CP0116201", 185),         # Oranges & similar citrus (whole navel)
    "lemon":     (212732, "CP0116299", 110),         # Other citrus (whole lemon)
    "avocado":   (212710, "CP0116199", 170),         # Other tropical fruits (whole Hass)
    "kiwi":      (212712, "CP0116501", 85),          # Other fruits n.e.c (whole)
    "melon":     (212736, "CP0116501", 1000),        # Other fruits n.e.c (whole melon)
    "pineapple": (212737, "CP0116199", 1100),        # Other tropical fruits (whole)
}


def weight_g(slug: str):
    """Standard whole-fruit weight (g) used to convert an ONS per-each price to £/kg,
    or None if ONS already quotes that fruit per kg. Lets the board flag the estimate."""
    cfg = ONS_ITEMS.get(slug)
    return cfg[2] if cfg and len(cfg) > 2 else None


class OnsRetailPrice(SignalSource):
    """Monthly UK retail £/kg for one fruit from the ONS Shopping Prices tool: the
    pre-2025 item-level £/kg, spliced forward by its consumption-segment price index
    (a documented proxy). Series `ons_<slug>_retail_price`; direct months key="",
    spliced months key="proxy_<segment>". Per-kg items only."""

    freq = "M"
    unit = "gbp_per_kg"

    def __init__(self, slug: str = "blueberry", item_id: int | None = None,
                 segment: str | None = None, weight_g: int | None = None):
        self.slug = slug
        self.series = f"ons_{slug}_retail_price"
        cfg = ONS_ITEMS.get(slug, (item_id, segment, weight_g))
        self.item_id, self.segment = (item_id or cfg[0]), (segment or cfg[1])
        self.weight_g = weight_g if weight_g is not None else (cfg[2] if len(cfg) > 2 else None)

    def fetch(self, vintage_date: _dt.date | None = None,
              old_xls: pd.ExcelFile | None = None, new_xls: pd.ExcelFile | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        old_xls = old_xls or pd.ExcelFile(io.BytesIO(self._get(_URL_OLD)))
        direct = _series_from_sheet(old_xls, "averageprice", self.item_id)
        if direct.empty:
            return self._tidy([], vintage_date)
        if self.weight_g:                               # per-each item → estimated £/kg
            direct = direct / (self.weight_g / 1000.0)  # (proxy rescales off this, stays £/kg)
        proxy = self._proxy_extension(direct, new_xls)
        records = [self._row(d, v, "") for d, v in direct.items()]
        records += [self._row(d, v, f"proxy_{self.segment}") for d, v in proxy.items()]
        return self._tidy(records, vintage_date)

    # -- helpers --
    def _proxy_extension(self, direct: pd.Series, new_xls: pd.ExcelFile | None) -> pd.Series:
        """Segment price index, rescaled to the item's £/kg level at the shared month."""
        try:
            new_xls = new_xls or pd.ExcelFile(io.BytesIO(self._get(_URL_NEW)))
            idx = _series_from_sheet(new_xls, "chained", self.segment)
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


class OnsRetailBlueberryPrice(OnsRetailPrice):
    """Back-compat shim for the pipeline/tests — the original blueberry source."""

    def __init__(self):
        super().__init__("blueberry")


def refresh_all(slugs=tuple(ONS_ITEMS)):
    """Download both ONS files ONCE and write each fruit's spliced £/kg to the vintage
    store. Returns {slug: n_rows}. Skips a fruit whose item has no £/kg (degrades)."""
    from ..store import vintage
    old_xls = pd.ExcelFile(io.BytesIO(OnsRetailPrice._get(_URL_OLD)))
    try:
        new_xls = pd.ExcelFile(io.BytesIO(OnsRetailPrice._get(_URL_NEW)))
    except Exception:                                   # noqa: BLE001 -- direct-only, don't fake
        new_xls = None
    out = {}
    for slug in slugs:
        df = OnsRetailPrice(slug).fetch(old_xls=old_xls, new_xls=new_xls)
        if not df.empty:
            vintage.save(df)
        out[slug] = len(df)
    return out


if __name__ == "__main__":
    import sys
    slugs = sys.argv[1:] or list(ONS_ITEMS)
    counts = refresh_all(slugs)
    for slug, n in counts.items():
        print(f"ons_{slug}_retail_price: {n} rows")
