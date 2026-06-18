"""Live retail blueberry price -- forward-collection, via the Trolley price index.

Why an aggregator: rather than fight each supermarket's bot protection, we read
one site that already tracks them all -- Trolley.co.uk -- which carries a per-
product price compared across Tesco/Sainsbury's/Asda/Ocado/Morrisons/Waitrose.
This finally makes the year-round, blueberry-specific in-season price real (the
ONS proxy is all-berries and monthly); it is the live continuation past Jan 2025.

Robots-compliant by construction: Trolley's robots.txt disallows /search/, so we
NEVER crawl search. Instead we poll a curated, fixed basket of /product/ pages
(explicitly allowed), discovered once out-of-band via a web search engine. Each
product page exposes a clean schema.org JSON-LD Product block (name with pack
size + offers.price in GBP); we read that, not scraped HTML, so it is stable.
Adding products is a manual edit to BASKET (keeps us off /search/).

Honesty unchanged: this has NO history before today -- it only accrues forward,
so it cannot feed the walk-forward backtest; its job is to start the clock and,
going forward, validate/replace the all-berries ONS proxy. Retail price is also
demand-driven and does not lead volume -- an economics/context signal. If every
product fails to parse, it emits an empty frame rather than faking a number.
"""
from __future__ import annotations

import datetime as _dt
import html
import json
import re
import time

import pandas as pd
import requests

from .base import SignalSource

_BASE = "https://www.trolley.co.uk/product/"
# Curated fresh-blueberry basket (retailer, tier, /product/ path). Discovered once
# via web search; only these allowed product pages are ever fetched.
BASKET = [
    ("Sainsbury's", "standard", "sainsburys-blueberries/WMT802"),
    ("Tesco", "standard", "tesco-blueberries/IBD496"),
    ("Tesco", "standard", "tesco-blueberries/SMH653"),
    ("Tesco", "standard", "tesco-blueberries/HRN985"),
    ("Tesco", "organic", "tesco-organic-blueberries/JMA096"),
    ("Tesco", "finest", "tesco-finest-blueberries-class-1/DUX280"),
    ("Asda", "standard", "asda-sweet-bursting-blueberries/GSX127"),
    ("Asda", "standard", "asda-sweet-bursting-blueberries/GDA152"),
]
_HEADERS = {
    "User-Agent": "uk-blueberry-nowcast/0.1 (research; contact via repo)",
    "Accept": "text/html", "Accept-Language": "en-GB,en;q=0.9",
}
_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_SIZE = re.compile(r"\(([\d.]+)\s*(g|kg)\)", re.I)


def _grams(name: str) -> float | None:
    m = _SIZE.search(name)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1000 if m.group(2).lower() == "kg" else v


def _parse(page_html: str) -> tuple[float, float] | None:
    """(price_gbp, grams) from the product page's JSON-LD, or None if unusable."""
    m = _LD.search(page_html)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        price = float(d["offers"]["price"])
        grams = _grams(html.unescape(str(d.get("name", ""))))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if not grams or price <= 0:
        return None
    return price, grams


class RetailBlueberryPrice(SignalSource):
    series = "retail_blueberry_price"
    freq = "W"
    unit = "gbp_per_kg"

    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        week = (vintage_date - _dt.timedelta(days=vintage_date.weekday())).isoformat()

        records = []
        for retailer, tier, path in BASKET:
            parsed = self._fetch_product(_BASE + path)
            if parsed is None:
                continue
            price, grams = parsed
            records.append({
                "series": self.series, "ref_period": week, "freq": self.freq,
                "key": f"{retailer}|{tier}|{int(grams)}g",
                "value": round(price / (grams / 1000), 4), "unit": self.unit,
            })
            time.sleep(1.0)                             # polite: one product/sec
        return self._tidy(records, vintage_date)

    @staticmethod
    def _fetch_product(url: str) -> tuple[float, float] | None:
        for attempt in range(3):
            try:
                r = requests.get(url, headers=_HEADERS, timeout=30)
                r.raise_for_status()
                return _parse(r.text)
            except Exception:                           # noqa: BLE001 -- skip, don't fake
                time.sleep(2 ** attempt)
        return None


if __name__ == "__main__":
    df = RetailBlueberryPrice().fetch()
    if df.empty:
        print("retail_blueberry_price: 0 rows (all products failed to parse)")
    else:
        print(f"retail_blueberry_price: {len(df)} products, week {df['ref_period'].iloc[0]}")
        print(df[["key", "value"]].to_string(index=False))
        print(f"median GBP/kg: {df['value'].median():.2f}")
