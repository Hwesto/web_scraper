"""Weekly calendar grid + monthly cumulator bookkeeping.

The model state evolves weekly, but the only ground truth (HMRC) is a monthly
sum. We bridge the two with a cumulator variable (Harvey; Mariano-Murasawa): an
``accum`` state that sums weekly volume within a month and resets at each month
boundary. HMRC then observes ``accum`` at the last week of the month.

This module builds the weekly grid spanning a date range and, for each week,
the two facts the state-space needs:
  - xi_t  : cumulator carry, 0 on the first week of a new month else 1
            (accum_t = xi_t * accum_{t-1} + v_t)
  - is_month_end : True on the last week of a month -> carries the HMRC obs

Week -> month assignment uses the week's midpoint (Thursday), so a week belongs
to whichever month contains most of it. Boundary leakage (a week straddling two
months) is a small approximation absorbed by HMRC observation noise.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

import pandas as pd

WEEKS_PER_YEAR = 365.25 / 7.0  # 52.18, used for the seasonal angular frequency


@dataclass
class WeekGrid:
    weeks: pd.DatetimeIndex      # Monday-anchored week start dates
    month_key: list[str]         # "YYYY-MM" each week is assigned to
    xi: list[int]                # cumulator carry (0 resets, 1 carries)
    is_month_end: list[bool]     # last week of its month

    def __len__(self) -> int:
        return len(self.weeks)

    def index_of_month_end(self, month_key: str) -> int | None:
        """Row index of the month-end week for 'YYYY-MM', or None."""
        for i in range(len(self.weeks) - 1, -1, -1):
            if self.is_month_end[i] and self.month_key[i] == month_key:
                return i
        return None


def _midpoint_month(week_start: _dt.date) -> str:
    mid = week_start + _dt.timedelta(days=3)  # Thursday
    return f"{mid.year:04d}-{mid.month:02d}"


def build_week_grid(start: _dt.date, end: _dt.date) -> WeekGrid:
    """Weekly grid (Mondays) covering [start, end], with cumulator metadata."""
    first_monday = start - _dt.timedelta(days=start.weekday())
    weeks = pd.date_range(first_monday, end, freq="W-MON")

    month_key = [_midpoint_month(w.date()) for w in weeks]
    is_month_end = [
        i == len(month_key) - 1 or month_key[i] != month_key[i + 1]
        for i in range(len(month_key))
    ]
    # xi resets (0) on the first week of each month, carries (1) otherwise.
    xi = [1] * len(month_key)
    for i in range(len(month_key)):
        if i == 0 or month_key[i] != month_key[i - 1]:
            xi[i] = 0
    return WeekGrid(weeks=weeks, month_key=month_key, xi=xi, is_month_end=is_month_end)
