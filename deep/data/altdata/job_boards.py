"""Packhouse hiring collector -- experimental forward-collection leading signal.

Rationale: berry packhouses post temp roles ("fruit intake QC", "nightshift
repacker") ~1-2 weeks before a volume wave hits. This is free, legal, public,
and matches this repo's scraping competence -- the best surviving alt-data idea.

IMPORTANT -- this signal has NO history. It only exists from the day we start
scraping, so it can NEVER contribute to the walk-forward backtest that proves
the model against seasonal-naive. Its sole job in v1 is to START THE CLOCK: take
a timestamped count snapshot now so a vintage accrues for forward validation
next season. It is wired as a SignalSource but kept out of the core filter and
out of the M3 gate criteria.

This is a deliberate stub: it defines the schema, the query terms, and the
snapshot mechanics. The live scrape per board (gov.uk Find a Job, Indeed,
agency/packhouse career pages) is a TODO to fill in once M1-M3 are signed off.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

from ..base import SignalSource

# Search terms that flag a produce-intake labour surge.
ROLE_TERMS = [
    "fruit intake quality control",
    "nightshift repacker",
    "berry packer",
    "produce packhouse operative",
    "fruit packing seasonal",
]

# Packhouse / berry-cluster regions to geo-scope counts to.
REGION_TERMS = ["Kent", "Sittingbourne", "Herefordshire", "Angus", "West Sussex"]


class PackhouseHiringSignal(SignalSource):
    """Weekly count of berry-packhouse temp job postings (forward-collected)."""

    series = "packhouse_hiring"
    freq = "W"
    unit = "count"

    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        vintage_date = vintage_date or _dt.date.today()
        # TODO(M5): scrape each board for ROLE_TERMS x REGION_TERMS, dedupe by
        # posting id, count active postings. Until implemented, emit an empty
        # tidy frame so the pipeline runs and the schema/contract is fixed.
        records: list[dict] = []
        return self._tidy(records, vintage_date)


if __name__ == "__main__":
    df = PackhouseHiringSignal().fetch()
    print(f"packhouse_hiring rows: {len(df)} (stub -- forward collection not yet live)")
