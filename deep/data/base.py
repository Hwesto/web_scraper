"""SignalSource: the pluggable interface every estimator implements.

The fusion model treats each signal as a noisy, lagged, scaled readout of the
latent flow. Concretely that means every source must be able to answer one
question: "what did you know, and when did you know it?" -- i.e. produce a tidy
frame of observations each stamped with the real-world date it became available
(its vintage). The walk-forward backtest depends on this and nothing else.
"""
from __future__ import annotations

import abc
import datetime as _dt

import pandas as pd

# Canonical tidy schema returned by every source. Keeping it uniform is what
# lets the filter and the vintage store stay signal-agnostic.
#   series        str   -- stable id, e.g. "hmrc_blueberry_imports"
#   ref_period    str   -- ISO date of the period the value describes (week/month start)
#   freq          str   -- "W" weekly | "M" monthly
#   key           str   -- disaggregation key (e.g. origin name); "" if none
#   value         float -- the observation (tonnes, GBP/kg, count, ...)
#   unit          str   -- "tonnes" | "gbp_per_kg" | "count" ...
#   vintage_date  str   -- ISO date this value first became available to us
TIDY_COLUMNS = ["series", "ref_period", "freq", "key", "value", "unit", "vintage_date"]


class SignalSource(abc.ABC):
    """Base class for every data source feeding the nowcast."""

    #: stable identifier used as the series name and store partition
    series: str = "unnamed"
    #: observation frequency, "W" or "M"
    freq: str = "W"
    #: unit of the value column
    unit: str = "value"

    @abc.abstractmethod
    def fetch(self, vintage_date: _dt.date | None = None) -> pd.DataFrame:
        """Return observations as a tidy frame (see TIDY_COLUMNS).

        ``vintage_date`` defaults to today and stamps every returned row. Sources
        that can only observe "now" (scrapers) ignore any past date and stamp
        today; sources backed by a revision archive may honour it.
        """

    # -- shared helpers --
    @staticmethod
    def _tidy(records: list[dict], vintage_date: _dt.date) -> pd.DataFrame:
        """Coerce a list of partial dicts into the canonical tidy schema."""
        frame = pd.DataFrame(records)
        if frame.empty:
            return pd.DataFrame(columns=TIDY_COLUMNS)
        frame["vintage_date"] = vintage_date.isoformat()
        for col in TIDY_COLUMNS:
            if col not in frame.columns:
                frame[col] = ""
        return frame[TIDY_COLUMNS]
