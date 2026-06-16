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

    # --- price: observed recent trend + supply-implied pressure ---
    price = _ons_price_monthly()
    price = price[price.index <= target]
    price_level = float(price.iloc[-1]) if len(price) else float("nan")
    price_trend = (float(price.iloc[-1] / price.iloc[-4] - 1) * 100
                   if len(price) >= 4 else float("nan"))
    elast = _supply_price_elasticity(hmrc, _ons_price_monthly())
    implied_move = elast * anomaly * 100 if anomaly == anomaly else float("nan")  # %

    lean = "FLAT"
    if anomaly == anomaly:
        if anomaly > _ANOM:
            lean = "DOWN"
        elif anomaly < -_ANOM:
            lean = "UP"
    action = {"DOWN": "move volume now (sell ahead of the dip)",
              "UP": "lock price / cover now (before it firms)",
              "FLAT": "hold -- no clear supply edge this period"}[lean]

    return {
        "as_of": as_of.isoformat(), "origin": origin, "landing_month": f"{target.year}-{target.month:02d}",
        "in_season": bool(in_season),
        "arrivals_nowcast_t": round(nowcast_t, 0), "seasonal_norm_t": round(norm_t, 0) if norm_t == norm_t else None,
        "anomaly_pct": round(anomaly * 100, 0) if anomaly == anomaly else None,
        "supply_signal": supply, "confidence": "validated nowcast (~2wk lead, +12% OOS)" if in_season
        else "off-season -- lane not shipping",
        "price_level_gbp_kg": round(price_level, 2) if price_level == price_level else None,
        "price_trend_pct_3m": round(price_trend, 1) if price_trend == price_trend else None,
        "price_lean": lean, "implied_price_move_pct": round(implied_move, 1) if implied_move == implied_move else None,
        "elasticity_used": round(elast, 2), "action": action,
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
    mv = call["implied_price_move_pct"]
    mag = (f"~{abs(mv):.0f}%" if mv is not None else "modestly")
    direction = {"DOWN": "down", "UP": "up", "FLAT": "broadly flat"}[call["price_lean"]]
    return (
        f"THIS WEEK'S CALL  |  {call['origin']} arrivals, {call['landing_month']}\n"
        f"  Supply: {call['arrivals_nowcast_t']:.0f} t vs {call['seasonal_norm_t']:.0f} t normal "
        f"= {a:+.0f}%  [{call['supply_signal']}]   ({call['confidence']})\n"
        f"  Price:  {call['price_level_gbp_kg']} GBP/kg, {trend_word} ({trend:+.0f}% 3m)\n"
        f"  READ:   {heavy} {call['origin']} arrivals + {trend_word} cost -> UK price likely "
        f"{direction} {mag} over 2-3 wks -> {call['action']}.\n"
        f"  (supply = validated nowcast; price magnitude = rough elasticity, demand assumed stable)"
    )


if __name__ == "__main__":
    for d in [_dt.date(2025, 1, 20), _dt.date(2025, 2, 18), _dt.date.today()]:
        print("\n" + "=" * 70)
        print(render(weekly_call(d)))
