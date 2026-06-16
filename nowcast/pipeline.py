"""CLI entry point for the nowcast pipeline.

M1 implements `ingest`: pull every registered SignalSource and persist each as a
dated snapshot in the append-only vintage store. Running it daily is what builds
the revision history the backtest later replays. `calibrate`, `backtest` and
`nowcast` land in M2-M3.
"""
from __future__ import annotations

import argparse
import datetime as _dt

from .backtest.replay import load_origin_series, run_backtest, summarize
from .data.defra_price import DefraBlueberryPrice
from .data.hmrc import HmrcBlueberryImports
from .data.ons_price import OnsRetailBlueberryPrice
from .data.retail_price import RetailBlueberryPrice
from .data.altdata.job_boards import PackhouseHiringSignal
from .store import vintage

# Registry of sources. Core signals feed the filter; collect-only signals just
# accrue forward history and never enter the M3 gate.
CORE_SOURCES = [HmrcBlueberryImports(), DefraBlueberryPrice(), OnsRetailBlueberryPrice()]
COLLECT_ONLY_SOURCES = [PackhouseHiringSignal(), RetailBlueberryPrice()]


def cmd_ingest(_args: argparse.Namespace) -> None:
    today = _dt.date.today()
    for source in CORE_SOURCES + COLLECT_ONLY_SOURCES:
        try:
            frame = source.fetch(today)
        except Exception as exc:  # network/source failure shouldn't kill the run
            print(f"  [FAIL] {source.series}: {exc}")
            continue
        path = vintage.save(frame)
        span = (
            f"{frame['ref_period'].min()}..{frame['ref_period'].max()}"
            if not frame.empty else "empty"
        )
        where = path.name if path else "(nothing to save)"
        print(f"  [ok]   {source.series}: {len(frame)} rows [{span}] -> {where}")


def cmd_show(args: argparse.Namespace) -> None:
    frame = vintage.latest(args.series)
    print(f"{args.series}: {len(frame)} rows, vintages={vintage.vintages(args.series)}")
    if not frame.empty:
        print(frame.tail(args.n).to_string(index=False))


def cmd_backtest(args: argparse.Namespace) -> None:
    series = load_origin_series(args.origin)
    print(f"{args.origin}: n={len(series)} "
          f"[{series.index.min().date()}..{series.index.max().date()}], K={args.k}")
    summ = summarize(run_backtest(series, k=args.k, min_train=args.min_train))
    cols = ["h", "n", "model_mae", "seasonal_naive_mae", "skill_vs_seasonal_naive_%",
            "skill_vs_arima_%", "dir_skill_%", "cov80_%"]
    print(summ[cols].round(1).to_string(index=False))
    gate = summ.loc[summ["h"] == 1, "skill_vs_seasonal_naive_%"]
    verdict = "PASS" if (not gate.empty and gate.iloc[0] > 0) else "FAIL"
    print(f"\nGate (beat seasonal-naive at h=1): {verdict}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="nowcast")
    sub = parser.add_subparsers(required=True)

    p_ingest = sub.add_parser("ingest", help="pull all sources -> vintage store")
    p_ingest.set_defaults(func=cmd_ingest)

    p_show = sub.add_parser("show", help="show latest stored view of a series")
    p_show.add_argument("series")
    p_show.add_argument("-n", type=int, default=12)
    p_show.set_defaults(func=cmd_show)

    p_bt = sub.add_parser("backtest", help="walk-forward backtest vs benchmarks")
    p_bt.add_argument("origin", help="e.g. Morocco, Spain")
    p_bt.add_argument("-k", type=int, default=3, help="seasonal harmonics")
    p_bt.add_argument("--min-train", type=int, default=24)
    p_bt.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
