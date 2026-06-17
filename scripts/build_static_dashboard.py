"""Render the dashboard to a self-contained docs/index.html for GitHub Pages.

Design: PROVE the edge, don't just plot data. Centrepiece is the track record
(our ~2-week-early call vs the HMRC figure that landed later, vs the naive
baseline). Everything else is framed as deviation-from-normal, the thing that
drives a decision. Reads only committed data; the cron regenerates it.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from nowcast.backtest.within_month import _hmrc_chile, calibrated_run
from nowcast.call import weekly_call
from nowcast.config import REPO_ROOT
from nowcast.price import chile_fob_weekly
from nowcast.store import vintage

OUT = REPO_ROOT / "docs" / "index.html"
_BLUE, _GREY, _GREEN, _RED = "#1f6feb", "#8b949e", "#1a7f37", "#cf222e"
_LAYOUT = dict(template="plotly_white", margin=dict(l=10, r=10, t=40, b=10), height=360,
               legend=dict(orientation="h", y=1.12, x=0))


def _latest_in_season() -> dict:
    d = _dt.date.today().replace(day=1)
    for _ in range(18):
        c = weekly_call(d)
        if c["in_season"]:
            return c
        d = (pd.Timestamp(d) - pd.DateOffset(months=1)).date()
    return weekly_call(_dt.date.today())


def _html(fig, first=False):
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if first else False,
                       config={"displayModeBar": False})


# ---------- 1. PROOF: track record (nowcast vs actual vs naive) ----------
def fig_track_record(cr: dict):
    t = cr["table"].copy()
    t = t[t["seasonal_norm"] >= 100]                      # in-season only
    x = t["month"]
    fig = go.Figure()
    fig.add_bar(x=x, y=t["actual"], name="HMRC actual (truth)", marker_color="#d0d7de")
    fig.add_scatter(x=x, y=t["origin_nowcast"], name="Our call (~2 wks early)",
                    mode="lines+markers", line=dict(color=_BLUE, width=3))
    fig.add_scatter(x=x, y=t["seasonal_naive"], name="Naive 'same as last year'",
                    mode="lines", line=dict(color=_GREY, width=1.5, dash="dot"))
    fig.update_layout(**_LAYOUT, title="Our early call vs the official figure (Chile, tonnes/mo)",
                      yaxis_title="t/month")
    return fig


# ---------- 2. Arrivals vs seasonal-normal band ----------
def fig_vs_normal(s: pd.Series, label: str, unit: str):
    s = s.sort_index()
    df = pd.DataFrame({"v": s}); df["m"] = df.index.month
    norm = df.groupby("m")["v"].median()
    lo = df.groupby("m")["v"].quantile(0.1); hi = df.groupby("m")["v"].quantile(0.9)
    recent = s[s.index >= s.index.max() - pd.DateOffset(months=29)]
    rx = recent.index
    fig = go.Figure()
    fig.add_scatter(x=rx, y=[hi[m] for m in rx.month], name="normal range (10–90%)",
                    line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=rx, y=[lo[m] for m in rx.month], name="normal range",
                    fill="tonexty", fillcolor="rgba(140,148,158,0.20)",
                    line=dict(width=0), hoverinfo="skip")
    fig.add_scatter(x=rx, y=[norm[m] for m in rx.month], name="seasonal normal",
                    line=dict(color=_GREY, dash="dot"))
    fig.add_scatter(x=rx, y=recent.values, name=label, mode="lines+markers",
                    line=dict(color=_BLUE, width=3))
    fig.update_layout(**_LAYOUT, title=f"{label} vs seasonal normal", yaxis_title=unit)
    return fig


# ---------- 3. Supply calendar (origin x month heatmap) ----------
def fig_calendar():
    f = vintage.latest("hmrc_blueberry_imports").copy()
    f["d"] = pd.to_datetime(f["ref_period"]); f["m"] = f["d"].dt.month
    f = f[f["d"] >= f["d"].max() - pd.DateOffset(months=36)]
    top = f.groupby("key")["value"].sum().sort_values(ascending=False).head(7).index
    piv = (f[f["key"].isin(top)].groupby(["key", "m"])["value"].mean()
           .unstack(fill_value=0).reindex(top))
    piv = piv.reindex(columns=range(1, 13), fill_value=0)
    months = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    fig = go.Figure(go.Heatmap(z=piv.values, x=months, y=list(piv.index),
                               colorscale="Blues", showscale=False))
    fig.update_layout(**{**_LAYOUT, "height": 300},
                      title="Supply calendar — who lands when (avg t/mo, last 3 yrs)")
    return fig


def build() -> None:
    c = _latest_in_season()
    cr = calibrated_run()
    insk = cr["in_season"]["origin_nowcast"]
    chile = _hmrc_chile(); chile = chile[chile.index >= "2019-01-01"]
    fob = chile_fob_weekly(); fob = fob[fob > 0]
    fob_m = fob.resample("MS").mean() if len(fob) else fob

    # hero reasoning
    if c["in_season"]:
        tight = c["supply_signal"].split()[0]
        fobt = c["fob_trend_pct"]
        why = (f"Chilean fruit landing in ~2 weeks: <b>{c['arrivals_nowcast_t']:,.0f} t</b> — "
               f"<b>{c['anomaly_pct']:+.0f}%</b> vs the seasonal norm [<b>{tight}</b>]. "
               f"FOB cost <b>${c['fob_usd_kg']:.2f}/kg</b>"
               + (f", {'falling' if fobt and fobt<0 else 'rising' if fobt and fobt>0 else 'steady'} "
                  f"{abs(fobt):.0f}% m/m. " if fobt is not None else ". ")
               + f"<b>→ {c['action']}.</b> "
               "<span class='muted'>You know this ~2 weeks before HMRC publishes it.</span>")
    else:
        why = "Off-season — no Chilean fruit shipping. The track record and seasonal views below are year-round."

    headline = f"""<div class='stats'>
      <div class='stat'><div class='n'>~2 wks</div><div class='l'>earlier than HMRC</div></div>
      <div class='stat'><div class='n'>{insk['dir_skill_%']:.0f}%</div><div class='l'>directional hit-rate</div></div>
      <div class='stat'><div class='n'>+{insk['skill_vs_snaive_%']:.0f}%</div><div class='l'>more accurate than 'last year'</div></div>
      <div class='stat'><div class='n'>{cr['in_season']['n']}</div><div class='l'>in-season calls tested</div></div>
    </div>"""

    html = _TPL.format(
        landing=c["landing_month"], why=why, headline=headline,
        track=_html(fig_track_record(cr), first=True),
        arrivals=_html(fig_vs_normal(chile, "Chile arrivals", "t/month")),
        fob=_html(fig_vs_normal(fob_m, "Chile FOB cost", "USD/kg")) if len(fob_m) else "<p>FOB pending.</p>",
        calendar=_html(fig_calendar()),
        generated=_dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html)//1024} KB)")


_TPL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>UK Blueberry Intelligence</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f8fa;color:#1f2328}}
 .wrap{{max-width:1040px;margin:0 auto;padding:20px}}
 h1{{font-size:1.5rem;margin:.1em 0}} h2{{font-size:1.05rem;margin:1.5em 0 .3em}}
 .muted{{color:#57606a}} .lede{{color:#57606a;font-size:.9rem;margin-bottom:14px}}
 .call{{background:#fff;border:1px solid #d0d7de;border-left:5px solid #1a7f37;border-radius:10px;padding:16px 18px;font-size:1.05rem;line-height:1.5}}
 .stats{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
 .stat{{background:#0d1117;color:#fff;border-radius:10px;padding:12px 18px;flex:1;min-width:130px;text-align:center}}
 .stat .n{{font-size:1.6rem;font-weight:700;color:#58a6ff}} .stat .l{{font-size:.78rem;color:#c9d1d9}}
 .panel{{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:10px;margin-top:6px}}
 .cap{{color:#57606a;font-size:.82rem;margin:4px 2px 0}}
 .ledger{{display:flex;gap:12px;flex-wrap:wrap}} .ledger>div{{flex:1;min-width:230px;background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:12px 16px;font-size:.86rem}}
</style></head><body><div class="wrap">
<h1>🫐 UK Blueberry Intelligence</h1>
<div class="lede">The edge: we call the Chilean import number ~2 weeks before HMRC, and beat 'same as last year'. Generated {generated}.</div>

<h2>This week's call — landing {landing}</h2>
<div class="call">{why}</div>

<h2>Does it work? — our early call vs the official figure</h2>
{headline}
<div class="panel">{track}</div>
<div class="cap">Blue = our nowcast made ~2 weeks before the print. Grey bars = HMRC actual (what later landed). Dotted = the naive 'same as last year' baseline we beat.</div>

<h2>Where we are vs normal</h2>
<div class="panel">{arrivals}</div>
<div class="cap">This season's Chilean arrivals against the 10–90% seasonal band. Below the band = tight supply; above = glut.</div>
<div class="panel">{fob}</div>
<div class="cap">Landed FOB cost vs its seasonal band (declared export price, ~2-week lead). High = expensive fruit incoming.</div>

<h2>Supply calendar — who lands when</h2>
<div class="panel">{calendar}</div>
<div class="cap">Deep-sea Peru/Chile (Sep–Apr) hand off to Morocco/Spain (spring). The tool is live-leading on the deep-sea lanes, HMRC-anchored year-round.</div>

<h2>Confidence ledger</h2>
<div class="ledger">
 <div><b>● Validated edge</b><br>Within-month nowcast +12% vs naive, 66% directional, ~2-week lead. Reconciles to HMRC (0.1 kg). Origin↔HMRC corr 0.92.</div>
 <div><b>◐ Data-derived</b><br>FOB cost (8-yr). Named producers 91% / region 100% / cultivar 46%. Whole-market volume.</div>
 <div><b>⚠ Honest gaps / paid</b><br>UK sell-price direction doesn't back-test. Peru weekly + names = paid. Named certified orchard = paid CIREN.</div>
</div>
<div class="cap" style="margin-top:12px">5 clean negatives + 1 validated edge + 3 caught false-positives. The discipline is the product.</div>
</div></body></html>"""


if __name__ == "__main__":
    build()
