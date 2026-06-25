"""Cross-reference the SAG China-approved blueberry predios against our named flow.

SAG publishes ~71 blueberry predios authorised for export to China (named, with
CSG codes + region). It is the China-export subset, but the big multi-market
operations overlap with our UK-bound producers -- so for that overlap we tie our
flow to a NAMED + located + CSG-coded orchard. This computes the overlap and the
share of UK-bound volume it covers.

Schema-tolerant: pass the SAG CSV; if the producer/entity column isn't obvious,
name it explicitly with name_col.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import names
from ..config import REPO_ROOT

PRODUCER_CSV = REPO_ROOT / "data" / "weekly" / "chile_uk_blueberry_by_producer.csv"


def _pick_name_col(df: pd.DataFrame, name_col: str | None) -> str:
    if name_col:
        return name_col
    # heuristic: the non-numeric column with the longest average string (names)
    txt = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    if not txt:
        raise ValueError("no text column found; pass name_col explicitly")
    return max(txt, key=lambda c: df[c].astype(str).str.len().mean())


def crossref(sag_csv: str | Path, producer_csv: str | Path = PRODUCER_CSV,
             name_col: str | None = None, threshold: float = 0.5) -> dict:
    prod = pd.read_csv(producer_csv)
    sag = pd.read_csv(sag_csv)
    col = _pick_name_col(sag, name_col)
    roster = sag[col].dropna().astype(str).unique().tolist()

    rows = []
    for _, p in prod.iterrows():
        match, score = names.best_match(p["producer"], roster, threshold)
        rows.append({"producer": p["producer"], "net_kg": p["net_kg"],
                     "top_region": p.get("top_region"), "top_cultivar": p.get("top_cultivar"),
                     "sag_predio": match, "score": score, "china_approved": match is not None})
    res = pd.DataFrame(rows)
    total = res["net_kg"].sum()
    matched_kg = res.loc[res["china_approved"], "net_kg"].sum()
    return {
        "n_producers": len(res), "n_matched": int(res["china_approved"].sum()),
        "sag_predios": len(roster), "name_col": col,
        "uk_kg_covered_%": round(100 * matched_kg / total, 1) if total else 0.0,
        "matched": res[res["china_approved"]].sort_values("net_kg", ascending=False),
        "table": res,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m nowcast.farm.sag_china <sag_china.csv> [name_col]")
        raise SystemExit(1)
    r = crossref(sys.argv[1], name_col=sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"SAG predios: {r['sag_predios']} | our producers: {r['n_producers']} | "
          f"matched: {r['n_matched']} | UK volume covered by China-approved orchards: "
          f"{r['uk_kg_covered_%']}%  (name col: {r['name_col']})")
    print(r["matched"][["producer", "net_kg", "top_region", "sag_predio", "score"]].to_string(index=False))
