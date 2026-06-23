"""The atlas registry schema — one machine-readable row per
commodity × country × role × data-point, flagged free / paid / none.

This replaces the per-lane markdown baselines (`baseline_*.md`), which don't
scale to global × multi-fruit. Each row says: *for this data point, on this
country's side of this commodity's trade, does a free source exist, a paid one
(named), or none at all* — plus whether we've actually wired it, and how deep /
granular / fresh it is.

The free/paid/none flag is the whole point: it is the structural ceiling on
what a free model can ever see, made queryable instead of prose.
"""
from __future__ import annotations

import pandas as pd

# The canonical column order (HANDOFF.md Phase-0/1 schema, + two practical extensions).
COLUMNS = [
    "commodity",      # join key to hs_codes (e.g. "blueberry")
    "hs_code",        # HS6 line (e.g. "081040")
    "country",        # area the data-point describes ("Chile", "United Kingdom", "*"=global)
    "role",           # exporter | importer | both | global
    "data_point",     # the thing being catalogued ("orchard area by variety", ...)
    "access",         # free | paid | none  <- the structural-ceiling flag
    "wired",          # yes | no | derived | probe | na  <- held & refreshing, or just known
    "source",         # provider / feed name
    "url",            # endpoint or page
    "granularity",    # spatial/temporal/entity grain ("block-level", "monthly", "named")
    "depth",          # time depth held/available ("2018->now", "1987->2024", "")
    "verified_date",  # last date the source was confirmed reachable/parseable ("" = unprobed)
    "notes",          # caveats, paid alternative, the asymmetry, etc.
]

ACCESS = {"free", "paid", "none"}
ROLES = {"exporter", "importer", "both", "global"}
WIRED = {"yes", "no", "derived", "probe", "na"}


def empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def validate(df: pd.DataFrame) -> list[str]:
    """Return a list of human-readable schema violations (empty == valid)."""
    issues: list[str] = []
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        issues.append(f"missing columns: {missing}")
        return issues                                  # can't check rows without columns
    extra = [c for c in df.columns if c not in COLUMNS]
    if extra:
        issues.append(f"unexpected columns: {extra}")

    bad_access = sorted(set(df["access"]) - ACCESS)
    if bad_access:
        issues.append(f"invalid access values: {bad_access}")
    bad_role = sorted(set(df["role"]) - ROLES)
    if bad_role:
        issues.append(f"invalid role values: {bad_role}")
    bad_wired = sorted(set(df["wired"]) - WIRED)
    if bad_wired:
        issues.append(f"invalid wired values: {bad_wired}")

    for col in ("commodity", "country", "data_point", "access", "role"):
        blank = df[df[col].astype(str).str.strip() == ""]
        if len(blank):
            issues.append(f"{len(blank)} row(s) with empty {col}")

    dups = df.duplicated(subset=["commodity", "country", "role", "data_point"])
    if dups.any():
        issues.append(f"{int(dups.sum())} duplicate (commodity,country,role,data_point) row(s)")
    return issues
