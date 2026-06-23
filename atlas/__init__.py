"""The atlas — a machine-readable catalogue of *what information exists* per
commodity × country × data-point, flagged free / paid / none.

This package is the breadth-first deliverable (see HANDOFF.md): a structured
registry that scales to global × multi-fruit, replacing the per-lane markdown
baselines. It hangs off three foundations (Phase 0/1):

- `hs_codes`     — commodity → HS6 + national CN8/CN10 splits (the join key).
- `registry`     — the atlas table itself (free|paid|none per data-point).
- `comtrade_sweep` — global exporter/importer ranking → the "global" target set.

`countries` is the shared M49 ↔ name lookup the whole package uses.
"""
from __future__ import annotations

from nowcast.config import DATA_DIR

ATLAS_DIR = DATA_DIR / "atlas"
