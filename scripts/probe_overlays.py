"""Re-probe every catalogued atlas source URL and log its live reachability.

Phase 2 catalogues national overlay sources but several are real yet
**anti-bot/503/TLS-blocked from the Claude sandbox** (StatCan CIMT, PL GUS/PIORIN,
MA ONSSA, MX SIAP, MA Office des Changes, ...). The HANDOFF rule: anything blocked
in the sandbox usually works from the **GitHub runner's clean egress** -- so this
script is meant to run there (see `.github/workflows/atlas-refresh.yml`).

It walks the registry's distinct source URLs, probes each (`atlas.probe`), and
writes `data/atlas/probe_log.csv` -- the live reachability record, kept separate
from `registry.csv` (which is seed-generated catalogue metadata, so a probe run
never fights the seed). Join the two on `url` to see which catalogued sources are
currently live from clean egress.

    python scripts/probe_overlays.py [--only-blank] [--delay 0.3]

`--only-blank` probes just the rows whose registry `verified_date` is empty (the
ones flagged for runner re-probe), which is the cheap weekly mode.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas import ATLAS_DIR, probe, registry

LOG = ATLAS_DIR / "probe_log.csv"
_COLS = ["url", "status", "detail", "access_hint", "probed_date",
         "n_rows", "countries", "example_data_point"]


def _url_context(df: pd.DataFrame) -> pd.DataFrame:
    """Distinct non-empty source URLs with the registry rows that cite them."""
    sub = df[df["url"].astype(str).str.strip() != ""]
    g = sub.groupby("url").agg(
        n_rows=("url", "size"),
        countries=("country", lambda s: ", ".join(sorted(set(s)))),
        example_data_point=("data_point", "first"),
    ).reset_index()
    return g


def run(only_blank: bool = False, delay: float = 0.3, timeout: int = 20) -> pd.DataFrame:
    df = registry.load()
    if only_blank:
        df = df[df["verified_date"].astype(str).str.strip() == ""]
    ctx = _url_context(df)
    rows = []
    for _, c in ctx.iterrows():
        rec = probe.probe(c["url"], timeout=timeout)
        rec.update({"n_rows": int(c["n_rows"]), "countries": c["countries"],
                    "example_data_point": c["example_data_point"]})
        rows.append(rec)
        print(f"{rec['status']:12s} {c['url']}")
        time.sleep(delay)
    out = pd.DataFrame(rows, columns=_COLS)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(LOG, index=False)
    return out


def load_log() -> pd.DataFrame:
    if not LOG.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(LOG)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-blank", action="store_true",
                    help="probe only rows with an empty verified_date (runner re-probe)")
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()
    out = run(only_blank=args.only_blank, delay=args.delay, timeout=args.timeout)
    print(f"\nprobed {len(out)} distinct URLs -> {LOG}")
    print(out["status"].value_counts().to_string())
