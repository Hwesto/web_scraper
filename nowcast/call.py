"""'This week's call' -- the hero panel that answers sell-now / hold / lock.

Built on the one VALIDATED signal: the within-month Chilean arrivals nowcast
(origin exports transit-shifted, ~2 weeks ahead of HMRC, +12% OOS vs seasonal-
naive). That gives supply vs normal, confidence-tagged. Price direction is a
TRANSPARENT inference on top (supply-pressure sign + observed recent price trend
+ a flagged elasticity) -- not a fabricated forecast; demand is assumed stable
and that caveat is surfaced.

weekly_call(as_of) -> structured call; render() -> the plain-English read line.
"""
from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from .backtest.within_month import _hmrc_chile, origin_implied_monthly
from .benchmarks import seasonal_naive
from .store import vintage

_LONG, _SHORT, _NORMAL = "LONG (heavy)", "SHORT (light)", "NORMAL"
_ANOM = 0.12            # +/-12% vs norm -> call it heavy/light
_INSEASON_T = 100.0     # tonnes/month below which the lane is effectively off-season


def _ons_price_monthly() -> pd.Series:
    f = vintage.latest("ons_blueberry_retail_price")
    if f.empty:
        return pd.Series(dtype=float)
    f = f.copy(); f["d"] = pd.to_datetime(f["ref_period"])
    return f.set_index("d")["value"].sort_index()


def _total_supply_anomaly(target: pd.Timestamp) -> float:
    """YoY anomaly of TOTAL UK blueberry supply (all origins) for the month --
    the basis price weakly tracks (vs Chile-only, which doesn't)."""
    f = vintage.latest("hmrc_blueberry_imports").copy()
    f["d"] = pd.to_datetime(f["ref_period"])
    tot = f.groupby("d")["value"].sum().sort_index()
    cur, prior = tot.get(target, np.nan), tot.get(target - pd.DateOffset(months=12), np.nan)
    return (cur - prior) / prior if (prior == prior and prior) else float("nan")


def _supply_price_elasticity(hmrc: pd.Series, price: pd.Series) -> float:
    """Rough %price per %volume from history (log-log YoY). LOW confidence --
    blueberry price/volume link is weak; used only for a directional magnitude."""
    j = pd.concat([hmrc.rename("v"), price.rename("p")], axis=1, sort=False).dropna()
    j = j[(j["v"] > _INSEASON_T) & (j["p"] > 0)]
    if len(j) < 18:
        return -0.3
    dv = np.log(j["v"]).diff(12); dp = np.log(j["p"]).diff(12)
    d = pd.concat([dv, dp], axis=1).dropna()
    if len(d) < 12 or d.iloc[:, 0].std() == 0:
        return -0.3
    beta = np.polyfit(d.iloc[:, 0], d.iloc[:, 1], 1)[0]
    return float(np.clip(beta, -1.5, 0.2))


def weekly_call(as_of: _dt.date | None = None, origin: str = "Chile",
                transit_weeks: int = 2) -> dict:
    as_of = as_of or _dt.date.today()
    target = pd.Timestamp(as_of.year, as_of.month, 1)

    hmrc = _hmrc_chile()
    implied = origin_implied_monthly(transit_weeks)
    train = hmrc[hmrc.index < target]
    # scale (origin export -> UK import) calibrated on the past only
    ov = pd.concat([train.rename("h"), implied.rename("e")], axis=1, sort=False).dropna()
    ov = ov[ov["e"] > 0]
    scale = float(ov["h"].sum() / ov["e"].sum()) if len(ov) and ov["e"].sum() else 1.0

    nowcast_t = scale * float(implied.get(target, 0.0))
    norm_t = float(seasonal_naive(train, 1)) if len(train) >= 12 else float("nan")
    in_season = nowcast_t >= _INSEASON_T or (norm_t == norm_t and norm_t >= _INSEASON_T)
    anomaly = (nowcast_t - norm_t) / norm_t if norm_t and norm_t == norm_t else float("nan")

    supply = _NORMAL
    if anomaly == anomaly:
        supply = _LONG if anomaly > _ANOM else _SHORT if anomaly < -_ANOM else _NORMAL

    # --- price: observed trend + a WEAK total-supply lean ---
    # Back-test (backtest/call_bt.py): the Chile-only price call is coin-flip
    # (48%); whole-market total supply is only marginally directional (~57%,
    # corr -0.17 at 2m). So price is a low-confidence DIRECTIONAL lean, not a
    # forecast, and it is driven by TOTAL UK supply (what price actually tracks).
    price = _ons_price_monthly()
    price = price[price.index <= target]
    price_level = float(price.iloc[-1]) if len(price) else float("nan")
    price_trend = (float(price.iloc[-1] / price.iloc[-4] - 1) * 100
                   if len(price) >= 4 else float("nan"))
    total_anom = _total_supply_anomaly(target)

    lean = "FLAT"
    if total_anom == total_anom:
        if total_anom > _ANOM:
            lean = "DOWN"
        elif total_anom < -_ANOM:
            lean = "UP"
    # Action is led by the VALIDATED supply signal (not the weak price lean).
    action = {_SHORT: "tight Chilean arrivals -- secure cover / lock supply now",
              _LONG: "ample Chilean arrivals -- no urgency; negotiate / delay buying",
              _NORMAL: "arrivals in line with normal -- hold"}[supply]

    return {
        "as_of": as_of.isoformat(), "origin": origin, "landing_month": f"{target.year}-{target.month:02d}",
        "in_season": bool(in_season),
        "arrivals_nowcast_t": round(nowcast_t, 0), "seasonal_norm_t": round(norm_t, 0) if norm_t == norm_t else None,
        "anomaly_pct": round(anomaly * 100, 0) if anomaly == anomaly else None,
        "supply_signal": supply, "confidence": "validated nowcast (~2wk lead, +12% OOS)" if in_season
        else "off-season -- lane not shipping",
        "price_level_gbp_kg": round(price_level, 2) if price_level == price_level else None,
        "price_trend_pct_3m": round(price_trend, 1) if price_trend == price_trend else None,
        "price_lean": lean, "price_confidence": "WEAK -- directional only (~57% backtest, low conf)",
        "total_supply_anom_pct": round(total_anom * 100, 0) if total_anom == total_anom else None,
        "action": action,
    }


def render(call: dict) -> str:
    if not call["in_season"]:
        return (f"THIS WEEK'S CALL ({call['origin']}, {call['landing_month']}): "
                f"off-season -- no {call['origin']} fruit shipping. Watch the in-season lane.")
    a = call["anomaly_pct"]
    heavy = "Heavy" if call["supply_signal"].startswith("LONG") else \
            "Light" if call["supply_signal"].startswith("SHORT") else "Normal"
    trend = call["price_trend_pct_3m"]
    trend_word = ("softening" if trend is not None and trend < -1 else
                  "firming" if trend is not None and trend > 1 else "flat")
    direction = {"DOWN": "soft", "UP": "firm", "FLAT": "flat"}[call["price_lean"]]
    return (
        f"THIS WEEK'S CALL  |  {call['origin']} arrivals, {call['landing_month']}\n"
        f"  SUPPLY (the call): {call['arrivals_nowcast_t']:.0f} t vs {call['seasonal_norm_t']:.0f} t "
        f"normal = {a:+.0f}%  [{call['supply_signal']}]\n"
        f"                     {call['confidence']} -- 66% directional in back-test\n"
        f"  Price (context):   {call['price_level_gbp_kg']} GBP/kg, {trend_word} ({trend:+.0f}% 3m); "
        f"total-supply lean {direction} [WEAK ~57%, not a forecast]\n"
        f"  -> ACTION: {call['action']}.\n"
        f"  (supply nowcast is the validated edge; price direction does not back-test reliably "
        f"on free data -- treat as context, pair with your own cost read)"
    )


if __name__ == "__main__":
    for d in [_dt.date(2025, 1, 20), _dt.date(2025, 2, 18), _dt.date.today()]:
        print("\n" + "=" * 70)
        print(render(weekly_call(d)))
