"""HMRC Overseas Trade Statistics ingest -- the anchor and ground truth.

Pulls monthly blueberry (CN8 08104050) import volumes by origin from the live
HMRC OData API, aggregates the per-port breakdown to a monthly tonnage per
country, and returns the canonical tidy frame.

Vintage honesty: the live API only serves the *current* revision, so we can only
snapshot "today's view". True historical vintages accrue from the day we start
pulling -- documented, not faked. The store stamps each pull with today's date.
"""
from __future__ import annotations

import datetime as _dt
import time

import requests

from .base import SignalSource
from ..config import (
    COMMODITY_ID,
    HISTORY_START_MONTH,
    HMRC_API_BASE,
    HMRC_MAX_RETRIES,
    HMRC_PAGE_DELAY_S,
    KG_PER_TONNE,
    FLOW_EU_IMPORTS,
    FLOW_NONEU_IMPORTS,
    FLOW_EU_EXPORTS,
    FLOW_NONEU_EXPORTS,
)

_HEADERS = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)", "Accept": "application/json"}


def _get(url: str, params: dict | None = None) -> dict:
    """GET one OData page with polite retry/backoff on network or rate-limit."""
    delay = 2.0
    for attempt in range(1, HMRC_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            # 429 / rejection text -> back off and retry
            if attempt == HMRC_MAX_RETRIES:
                resp.raise_for_status()
        except requests.RequestException:
            if attempt == HMRC_MAX_RETRIES:
                raise
        time.sleep(delay)
        delay *= 2
    return {}


def _page_flow(flow_id: int, commodity_id: int = COMMODITY_ID) -> list[dict]:
    """Fetch every OTS row for a flow + commodity (ALL origins), paging nextLink.
    No country filter -> whole-market coverage, not just a curated few."""
    flt = (f"CommodityId eq {commodity_id} and FlowTypeId eq {flow_id} "
           f"and MonthId ge {HISTORY_START_MONTH}")
    params = {"$filter": flt, "$select": "MonthId,CountryId,Value,NetMass", "$top": "5000"}
    rows: list[dict] = []
    payload = _get(f"{HMRC_API_BASE}/OTS", params=params)
    rows.extend(payload.get("value", []))
    while payload.get("@odata.nextLink"):
        time.sleep(HMRC_PAGE_DELAY_S)
        payload = _get(payload["@odata.nextLink"])
        rows.extend(payload.get("value", []))
    return rows


_COUNTRY_CACHE: dict[int, str] = {}


def _country_name(cid: int) -> str:
    if not _COUNTRY_CACHE:
        url = f"{HMRC_API_BASE}/Country?$select=CountryId,CountryName"
        while url:
            j = _get(url)
            for c in j.get("value", []):
                _COUNTRY_CACHE[c["CountryId"]] = c["CountryName"]
            url = j.get("@odata.nextLink")
            if url:
                time.sleep(HMRC_PAGE_DELAY_S)
    return _COUNTRY_CACHE.get(cid, f"country_{cid}")


def _month_to_iso(month_id: int) -> str:
    """200103 -> '2001-03-01' (period start, ISO)."""
    year, month = divmod(month_id, 100)
    return _dt.date(year, month, 1).isoformat()


class HmrcBlueberryImports(SignalSource):
    """Monthly blueberry import tonnage by origin from HMRC OTS (ALL origins)."""

    freq = "M"
    unit = "tonnes"

    def __init__(self, commodity_id=COMMODITY_ID, slug="blueberry"):
        self.commodity_id = commodity_id
        self.series = f"hmrc_{slug}_imports"

    def fetch(self, vintage_date: _dt.date | None = None) -> "pd.DataFrame":  # noqa: F821
        vintage_date = vintage_date or _dt.date.today()
        _country_name(0)                       # warm the country map

        raw: list[dict] = []
        for flow_id in (FLOW_EU_IMPORTS, FLOW_NONEU_IMPORTS):
            raw.extend(_page_flow(flow_id, self.commodity_id))
            time.sleep(HMRC_PAGE_DELAY_S)

        # Aggregate the per-port rows -> one tonnage per (month, country).
        agg: dict[tuple[int, int], float] = {}
        for row in raw:
            mid = row["MonthId"]
            cid = row["CountryId"]
            net_kg = row.get("NetMass") or 0.0
            agg[(mid, cid)] = agg.get((mid, cid), 0.0) + net_kg

        records = [
            {
                "series": self.series,
                "ref_period": _month_to_iso(mid),
                "freq": self.freq,
                "key": _country_name(cid),
                "value": net_kg / KG_PER_TONNE,
                "unit": self.unit,
            }
            for (mid, cid), net_kg in agg.items()
        ]
        return self._tidy(records, vintage_date)


class HmrcBlueberryImportValue(SignalSource):
    """Monthly blueberry import VALUE (GBP) by origin -> with the volume series
    gives a reconciled import unit value (GBP/kg) per origin, free."""

    freq = "M"
    unit = "gbp"

    def __init__(self, commodity_id=COMMODITY_ID, slug="blueberry"):
        self.commodity_id = commodity_id
        self.series = f"hmrc_{slug}_import_value"

    def fetch(self, vintage_date: _dt.date | None = None) -> "pd.DataFrame":  # noqa: F821
        vintage_date = vintage_date or _dt.date.today()
        _country_name(0)
        raw: list[dict] = []
        for flow_id in (FLOW_EU_IMPORTS, FLOW_NONEU_IMPORTS):
            raw.extend(_page_flow(flow_id, self.commodity_id))
            time.sleep(HMRC_PAGE_DELAY_S)
        agg: dict[tuple[int, int], float] = {}
        for row in raw:
            key = (row["MonthId"], row["CountryId"])
            agg[key] = agg.get(key, 0.0) + (row.get("Value") or 0.0)
        records = [
            {"series": self.series, "ref_period": _month_to_iso(mid), "freq": self.freq,
             "key": _country_name(cid), "value": gbp, "unit": self.unit}
            for (mid, cid), gbp in agg.items()
        ]
        return self._tidy(records, vintage_date)


class HmrcBlueberryReExports(SignalSource):
    """Monthly UK blueberry RE-EXPORT tonnage by destination (HMRC export flows).

    The UK ships a small share of landed fresh blueberries back out (mostly EU
    dispatch to Ireland/Netherlands) -- a hub/transit signal. Flows 2 (EU
    dispatch) + 4 (non-EU export). Same CN8 08104050 as the import side.
    """

    freq = "M"
    unit = "tonnes"

    def __init__(self, commodity_id=COMMODITY_ID, slug="blueberry"):
        self.commodity_id = commodity_id
        self.series = f"hmrc_{slug}_reexports"

    def fetch(self, vintage_date: _dt.date | None = None) -> "pd.DataFrame":  # noqa: F821
        vintage_date = vintage_date or _dt.date.today()
        _country_name(0)
        raw: list[dict] = []
        for flow_id in (FLOW_EU_EXPORTS, FLOW_NONEU_EXPORTS):
            raw.extend(_page_flow(flow_id, self.commodity_id))
            time.sleep(HMRC_PAGE_DELAY_S)
        agg: dict[tuple[int, int], float] = {}
        for row in raw:
            key = (row["MonthId"], row["CountryId"])
            agg[key] = agg.get(key, 0.0) + (row.get("NetMass") or 0.0)
        records = [
            {"series": self.series, "ref_period": _month_to_iso(mid), "freq": self.freq,
             "key": _country_name(cid), "value": net_kg / KG_PER_TONNE, "unit": self.unit}
            for (mid, cid), net_kg in agg.items()
        ]
        return self._tidy(records, vintage_date)


if __name__ == "__main__":
    import pandas as pd

    df = HmrcBlueberryImports().fetch()
    pd.set_option("display.width", 120)
    print(f"rows: {len(df)}  origins: {sorted(df['key'].unique())}")
    print(f"period range: {df['ref_period'].min()} .. {df['ref_period'].max()}")
    print(df.sort_values("ref_period").tail(12).to_string(index=False))
