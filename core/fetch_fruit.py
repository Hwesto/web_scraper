"""Fetch one fruit's core board data into its per-fruit namespace.

For each fruit it pulls the HS-driven feeds — HMRC monthly imports/value/re-exports
(vintage series `hmrc_<slug>_*`), the Comtrade global trade map, FAOSTAT production,
and the per-origin export destinations — into `<slug>`-suffixed caches. The
fruit-specific extras (Trolley retail, DEFRA wholesale/production) are NOT fetched
here; the board degrades gracefully without them.

Run: python -m core.fetch_fruit cherry        # one fruit
     python -m core.fetch_fruit               # all non-blueberry fruits
"""
from __future__ import annotations

import sys

from deep.store import vintage
from deep.data import hmrc
from deep.data.hmrc import (HmrcBlueberryImports, HmrcBlueberryImportValue,
                            HmrcBlueberryReExports)
from deep.market import comtrade_global, production
from core import player_exports, uk_production
from core.fruit import FRUITS


def fetch(fruit) -> None:
    ids = fruit.commodity_ids or hmrc.discover_cn8(fruit.hs6)
    cn8 = ", ".join(f"{c:08d}" for c in ids)
    print(f"== {fruit.name} ({fruit.slug}, HS {fruit.hs6} / CN8 {cn8}) ==")
    for cls in (HmrcBlueberryImports, HmrcBlueberryImportValue, HmrcBlueberryReExports):
        src = cls(ids, fruit.slug)
        try:
            df = src.fetch()
            vintage.save(df)
            print(f"  {src.series}: {len(df)} rows [{df['ref_period'].min()}..{df['ref_period'].max()}]")
        except Exception as exc:
            print(f"  {src.series}: FAILED {type(exc).__name__}: {exc}")
    try:
        out = comtrade_global.refresh(hs=fruit.hs6, cache=fruit.cache("global_trade"))
        print(f"  global_trade: {len(out)} rows -> {fruit.cache('global_trade').name}")
    except Exception as exc:
        print(f"  global_trade: FAILED {type(exc).__name__}: {exc}")
    try:
        out = production.refresh(item=fruit.faostat_item, cache=fruit.cache("global_production"))
        print(f"  global_production: {len(out)} rows ({fruit.faostat_item})")
    except Exception as exc:
        print(f"  global_production: FAILED {type(exc).__name__}: {exc}")
    players = {fruit.supply_origins[n][0]: n for n in fruit.inseason}
    try:
        out = player_exports.refresh(players=players, hs=fruit.hs6,
                                     cache=fruit.cache("player_destinations"))
        print(f"  player_destinations: {len(out)} rows ({out['player'].nunique() if len(out) else 0} origins)")
    except Exception as exc:
        print(f"  player_destinations: FAILED {type(exc).__name__}: {exc}")
    if fruit.defra_production:
        try:
            df = uk_production.refresh(fruit.slug, fruit.defra_rows)
            latest = f"{df['production_kt'].dropna().iloc[-1]:.1f} kt" if not df.empty else "none"
            print(f"  uk_production: {len(df)} yrs (latest {latest})")
        except Exception as exc:
            print(f"  uk_production: FAILED {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    args = sys.argv[1:]
    targets = ([FRUITS[a] for a in args] if args
               else [f for f in FRUITS.values() if f.slug != "blueberry"])
    for f in targets:
        fetch(f)
