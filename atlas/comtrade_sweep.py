"""Comtrade global sweep — rank every blueberry exporter and importer, in two calls.

The HANDOFF key insight: UN Comtrade *is* the free global base layer. With
reporterCode left empty (= all reporters) and partnerCode=0 (= World), one
preview call returns every country's total blueberry trade for a year:
flow=X gives the exporter ranking, flow=M the importer ranking. That single
sweep both *defines* the "global" target set (countries making up ~95% of
trade) and *populates* every lane's headline flow + price at once -- so "global"
is a sweep, not lane-by-lane labour.

Caveats baked in:
- The preview endpoint **caps at 500 rows** and the all-reporters call also emits
  per-secondary-partner (re-export origin) breakdown rows, which blow past the cap
  and silently truncate major reporters. We pin `partner2Code=0` to get exactly
  the World-aggregate row per reporter -- uncapped, deterministic, USA included
  (see the `_URL` note; verified live 2026-06). We still dedup defensively.
- **Comtrade annual data is staggered**: the most recent ~2 years are still
  accumulating reports, so a top exporter can be missing or tiny. Verified live
  2026-06: in 2024 Peru (the true #1) is rank 50 because it hadn't reported yet,
  while 2023 is complete with Peru #1. So `target_set`/`ranking` default to the
  latest *non-provisional* year (year <= current_year - FINAL_LAG_YEARS), and
  rows carry a `provisional` flag. Pass `include_provisional=True` to override.
- Imports here are each country's *self-reported* imports (mirror gaps exist).
- Tiny lanes have unreliable unit values; ranking is by value/weight totals, and
  `target_set` works on value share, so small-N noise doesn't move the target.

Committed to `data/atlas/comtrade_global_ranking.csv`; read offline by the atlas.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR, countries, hs_codes

CACHE = ATLAS_DIR / "comtrade_global_ranking.csv"
# reporterCode= (empty) = all reporters; partnerCode=0 = World. partner2Code=0 is
# essential: without it the preview also returns per-secondary-partner (re-export
# origin) breakdown rows, which inflate the response past the 500-row cap and
# silently truncate major reporters (verified live 2026-06: the US, the #1
# importer, was dropped). Pinning partner2Code=0 returns exactly the aggregate
# row per reporter (~80-150 rows), uncapped and deterministic.
_URL = ("https://comtradeapi.un.org/public/v1/preview/C/A/HS"
        "?reporterCode=&period={yr}&cmdCode={hs}&flowCode={flow}"
        "&partnerCode=0&partner2Code=0&motCode=0&customsCode=C00")
_FLOW = {"exporter": "X", "importer": "M"}
_COLS = ["year", "role", "reporter_code", "country", "value_usd", "net_kg",
         "unit_usd_kg", "rank", "share", "cum_share", "provisional"]

# Comtrade annual data is only treated as final this many calendar years on;
# more recent years are provisional (staggered reporting -- see module docstring).
# Set to 3 from a live check: in mid-2026 the 2024 sweep still missed Peru (the
# #1 exporter, rank 50), while 2023 was complete -- i.e. ~18 months was not yet
# final, but ~30 months (2023) was.
FINAL_LAG_YEARS = 3
# Comtrade HS-classified blueberry data is usable from 2012 -- pull the full
# history so the atlas carries trajectories, not just a recent snapshot.
START_YEAR = 2012


def is_provisional(year: int, today: _dt.date | None = None) -> bool:
    today = today or _dt.date.today()
    return int(year) > today.year - FINAL_LAG_YEARS


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _fetch(flow: str, year: int, hs: str, retries: int = 4) -> list[dict]:
    url = _URL.format(yr=year, hs=hs, flow=flow)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("data", []) or []
        except Exception as e:                         # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade sweep failed (flow={flow} {year}): {last}")


def _rank_one(flow_role: str, year: int, hs: str, names: dict[int, str]) -> pd.DataFrame:
    rows = _fetch(_FLOW[flow_role], year, hs)
    out = []
    for r in rows:
        code = int(_num(r, "reporterCode"))
        if code == 0:                                  # 0 == World aggregate, skip
            continue
        val, wgt = _num(r, "primaryValue"), _num(r, "netWgt")
        if val <= 0:
            continue
        out.append({"year": year, "role": flow_role, "reporter_code": code,
                    "country": names.get(code, f"M49-{code}"),
                    "value_usd": val, "net_kg": wgt,
                    "unit_usd_kg": round(val / wgt, 4) if wgt > 0 else 0.0})
    df = pd.DataFrame(out).drop_duplicates(subset=["reporter_code"])   # preview dups
    df = df.sort_values("value_usd", ascending=False).reset_index(drop=True)
    total = df["value_usd"].sum()
    df["rank"] = df.index + 1
    df["share"] = (df["value_usd"] / total).round(5) if total else 0.0
    df["cum_share"] = df["share"].cumsum().round(5)
    df["provisional"] = is_provisional(year)
    return df[_COLS]


def refresh(years: list[int], commodity: str = "blueberry") -> pd.DataFrame:
    """Sweep exporter + importer rankings for each year; (re)write the cache."""
    hs = hs_codes.hs6(commodity)
    names = countries.name_map()
    parts = []
    for year in years:
        for role in ("exporter", "importer"):
            parts.append(_rank_one(role, year, hs, names))
            time.sleep(0.5)                            # polite between calls
    fresh = pd.concat(parts, ignore_index=True)
    if CACHE.exists() and not fresh.empty:
        old = pd.read_csv(CACHE)
        old = old[~old["year"].isin(years)]            # replace refreshed years wholesale
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "role", "rank"]).reset_index(drop=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def latest_year(role: str, include_provisional: bool = False) -> int:
    """The default reference year for a role: latest non-provisional one cached.

    Falls back to the latest cached year if every cached year is provisional
    (so the function still returns *something* usable, just flagged)."""
    df = load()
    df = df[df["role"] == role]
    if df.empty:
        return 0
    years = sorted(df["year"].unique())
    if not include_provisional:
        final = [y for y in years if not is_provisional(int(y))]
        if final:
            return int(max(final))
    return int(max(years))


def ranking(role: str, year: int | None = None,
            include_provisional: bool = False) -> pd.DataFrame:
    """The exporter or importer ranking for one year (latest *final* year if None)."""
    df = load()
    if df.empty:
        return df
    df = df[df["role"] == role]
    if year is None:
        year = latest_year(role, include_provisional)
    return df[df["year"] == year].sort_values("rank").reset_index(drop=True)


def coverage_by_year(role: str | None = None) -> pd.DataFrame:
    """Per-year data-quality lens: how many reporters filed, total trade value, and
    whether the year is still provisional. Makes the staggered-reporting lag visible
    (a year with far fewer reporters / much lower total is still filling in)."""
    df = load()
    if df.empty:
        return df
    if role is not None:
        df = df[df["role"] == role]
    g = (df.groupby(["role", "year"])
           .agg(reporters=("reporter_code", "nunique"),
                total_value_usd=("value_usd", "sum"))
           .reset_index())
    g["provisional"] = g["year"].apply(lambda y: is_provisional(int(y)))
    return g.sort_values(["role", "year"]).reset_index(drop=True)


def target_set(role: str, year: int | None = None, coverage: float = 0.95,
               include_provisional: bool = False) -> pd.DataFrame:
    """Countries that together make up `coverage` of trade -- the 'global' target.

    Returns the smallest top-ranked set whose cumulative value share first
    reaches `coverage`. This is the breadth the atlas must cover to be 'global'.
    Defaults to the latest non-provisional year so a half-reported recent year
    can't drop a top exporter (e.g. Peru in 2024) from the target.
    """
    df = ranking(role, year, include_provisional)
    if df.empty:
        return df
    keep = df[df["cum_share"] < coverage]
    # include the first row that crosses the threshold
    n = len(keep) + 1 if len(keep) < len(df) else len(df)
    return df.head(n).reset_index(drop=True)


if __name__ == "__main__":                             # python -m atlas.comtrade_sweep
    this = _dt.date.today().year
    # full history START_YEAR..present (recent years flagged provisional).
    df = refresh(list(range(START_YEAR, this + 1)))
    print(f"cached {len(df)} ranking rows ({START_YEAR}->{this}) -> {CACHE}")
    for role in ("exporter", "importer"):
        ts = target_set(role)                          # latest final year
        yr = int(ts["year"].iloc[0]) if len(ts) else "-"
        print(f"\n{role}s covering 95% of trade ({yr}, final): {len(ts)} countries")
        print(ts[["rank", "country", "value_usd", "net_kg", "share", "cum_share"]]
              .head(15).to_string(index=False))
