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
from .data.hmrc import (HmrcBlueberryImports, HmrcBlueberryImportValue,
                        HmrcBlueberryReExports)
from .data.ons_price import OnsRetailBlueberryPrice
from .data.retail_price import RetailBlueberryPrice, RetailPrice, BASKETS
from .data.altdata.job_boards import PackhouseHiringSignal
from .store import vintage
from .volume.data.odepa_chile import OdepaChileExports
from .volume.series import build_origin_volume, reconcile_error
from .volume.validate import two_sided_crosscheck

# Registry of sources. Core signals feed the filter; collect-only signals just
# accrue forward history and never enter the M3 gate.
CORE_SOURCES = [HmrcBlueberryImports(), HmrcBlueberryImportValue(), HmrcBlueberryReExports(),
                DefraBlueberryPrice(), OnsRetailBlueberryPrice(), OdepaChileExports()]
COLLECT_ONLY_SOURCES = [PackhouseHiringSignal(), RetailBlueberryPrice()]
# Atlas fruits' weekly shelf prices accrue forward history here too (same Trolley
# basket mechanism, weekly cadence — shelf £/kg moves week-to-week, unlike the heavy
# annual feeds that refresh monthly in core.fetch_fruit). Auto-derived from the
# baskets, minus blueberry (already covered by RetailBlueberryPrice above).
ATLAS_RETAIL_SOURCES = [RetailPrice(s) for s in BASKETS if s != "blueberry"]
COLLECT_ONLY_SOURCES += ATLAS_RETAIL_SOURCES


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


def cmd_call(args: argparse.Namespace) -> None:
    import datetime as _dt
    from .call import weekly_call, render
    as_of = _dt.date.fromisoformat(args.date) if args.date else _dt.date.today()
    print(render(weekly_call(as_of)))


def cmd_volume(args: argparse.Namespace) -> None:
    vol = build_origin_volume(args.origin, k=args.k)
    if vol.empty:
        print(f"{args.origin}: no data")
        return
    tiers = vol["confidence_tier"].value_counts().to_dict()
    print(f"{args.origin}: {len(vol)} weekly points, tiers={tiers}")
    cols = ["iso_week", "volume_kg", "confidence_tier",
            "control_total_month_kg", "band_low_kg", "band_high_kg"]
    print(vol[cols].tail(args.n).to_string(index=False))
    rec = reconcile_error(vol)
    print(f"\nmax reconciliation error: {rec['abs_err_kg'].max():.2f} kg (should be ~0)")
    if args.origin in ("Chile",):
        print("two-sided cross-check:", two_sided_crosscheck(args.origin))


def main() -> None:
    parser = argparse.ArgumentParser(prog="nowcast")
    sub = parser.add_subparsers(required=True)

    p_vol = sub.add_parser("volume", help="build reconciled weekly volume series")
    p_vol.add_argument("origin")
    p_vol.add_argument("-k", type=int, default=3)
    p_vol.add_argument("-n", type=int, default=10)
    p_vol.set_defaults(func=cmd_volume)

    p_call = sub.add_parser("call", help="this week's call (the hero panel)")
    p_call.add_argument("--date", default=None, help="as-of date YYYY-MM-DD")
    p_call.set_defaults(func=cmd_call)

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
