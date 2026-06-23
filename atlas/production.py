"""Production-snapshot layer -- patches FAOSTAT's gaps and corrects the world ranking.

FAOSTAT (atlas/faostat.py) is the production base layer, but it has real holes: it carries
NO China (the world #1 at ~810 kt), South Africa, or Argentina blueberry production. This
hand-curated snapshot (`data/atlas/production.csv` + China via atlas/china.py) fills the
gaps so the production picture is honest -- without it the atlas shows the USA as #1
producer (402 kt) when China grows twice that.

top_global() merges FAOSTAT (latest year) with the snapshots into the true ranking.
Snapshot, hand-refreshed -- same contract as the committees.
"""
from __future__ import annotations

import pandas as pd

from atlas import ATLAS_DIR, faostat

CACHE = ATLAS_DIR / "production.csv"


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=["country", "year", "metric", "value", "unit", "note", "source"])
    return pd.read_csv(CACHE)


def latest(country: str, metric: str = "production") -> float | None:
    df = load()
    sub = df[(df["country"] == country) & (df["metric"] == metric)].sort_values("year")
    return float(sub.iloc[-1]["value"]) if len(sub) else None


def top_global(n: int = 12) -> pd.DataFrame:
    """The TRUE world production ranking: FAOSTAT latest + snapshots (China, SA, Argentina)."""
    fa = faostat.load()
    rows = []
    if not fa.empty:
        fy = fa[fa["year"] == fa["year"].max()]
        rows = [(str(c).split("(")[0].strip(), v / 1000)                 # kt
                for c, v in zip(fy["country"], fy["production_t"]) if v > 0]
    have = {c for c, _ in rows}
    # China (world #1) from the China dossier
    try:
        from atlas import china
        cn = china.latest("production", "China total")
        if cn:
            rows.append(("China", cn / 1000))
    except Exception:
        pass
    # other FAOSTAT-missing producers from the snapshot
    snap = load()
    for _, r in snap[snap["metric"] == "production"].iterrows():
        if not any(r["country"] in h or h == r["country"] for h in have):
            rows.append((r["country"], float(r["value"]) / 1000))
    df = (pd.DataFrame(rows, columns=["country", "production_kt"])
          .groupby("country", as_index=False)["production_kt"].max()
          .sort_values("production_kt", ascending=False).reset_index(drop=True))
    df["production_kt"] = df["production_kt"].round(0)
    return df.head(n)


if __name__ == "__main__":
    print("TRUE world blueberry production (FAOSTAT + snapshots patching China/SA/Argentina):")
    print(top_global().to_string(index=False))
