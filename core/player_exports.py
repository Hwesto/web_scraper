"""View 2 — where each major UK-supply player ships, and at what price.

Per player: full destination split (% of their tonnage) + unit price ($/kg), annual,
from UN Comtrade (reporter=player). Annual is the resolution that's complete for ALL
players (monthly is patchy — Morocco especially); we anchor on the latest complete year.
Committed cache; the deep history per player lives in comtrade.py's caches for Chile/Peru.
"""
from __future__ import annotations

import pandas as pd

from deep.config import DATA_DIR, SUPPLY_ORIGINS, INSEASON_ORIGINS
from deep.market import comtrade

OUT = DATA_DIR / "market" / "player_destinations.csv"
# major UK-supply origins, reporter M49 -> name — derived from the per-fruit config.
PLAYERS = {SUPPLY_ORIGINS[n][0]: n for n in INSEASON_ORIGINS}


def refresh(year: int = 2024, players: dict | None = None, hs: str | None = None,
            cache=OUT) -> pd.DataFrame:
    players = PLAYERS if players is None else players
    rows = []
    for code, name in players.items():
        df = comtrade._fetch_year(year, code, hs=hs) if hs else comtrade._fetch_year(year, code)
        if df.empty:
            continue
        df = df[df["net_kg"] >= 50_000].copy()
        tot = df["net_kg"].sum()
        df["player"] = name
        df["year"] = year
        df["pct_tonnage"] = (df["net_kg"] / tot * 100).round(1)
        rows.append(df[["player", "year", "destination", "net_kg",
                        "cif_usd_kg", "pct_tonnage"]])
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True).sort_values(
        ["player", "net_kg"], ascending=[True, False])
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(cache, index=False)
    return out


def load(cache=OUT) -> pd.DataFrame:
    return pd.read_csv(cache) if cache.exists() else pd.DataFrame()


def by_player(name: str) -> pd.DataFrame:
    df = load()
    return df[df["player"] == name].reset_index(drop=True)


if __name__ == "__main__":
    out = refresh()
    print(f"wrote {len(out)} rows ({out['player'].nunique()} players) -> {OUT}")
    for p in PLAYERS.values():
        d = out[out["player"] == p].head(3)
        top = ", ".join(f"{r.destination} {r.pct_tonnage:.0f}%@${r.cif_usd_kg:.2f}" for r in d.itertuples())
        print(f"  {p:14} {top}")
