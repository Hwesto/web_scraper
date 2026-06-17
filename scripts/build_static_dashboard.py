"""Render the dashboard to a self-contained docs/index.html for GitHub Pages.

Reads only committed data (vintage store + weekly CSVs) + the model functions, so
the cron can regenerate it and GitHub Pages serves it free, auto-updating weekly.
Run: python scripts/build_static_dashboard.py
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # repo root -> import nowcast

import pandas as pd
import plotly.express as px

from nowcast.call import weekly_call
from nowcast.config import REPO_ROOT
from nowcast.price import chile_fob_weekly
from nowcast.volume.uk_total import build_uk_total

OUT = REPO_ROOT / "docs" / "index.html"
_REGION = {5: "Valparaíso", 6: "O'Higgins", 7: "Maule", 8: "Biobío", 9: "Araucanía",
           10: "Los Lagos", 13: "Metropolitana", 14: "Los Ríos", 16: "Ñuble"}
_PLOT = dict(template="plotly_white", margin=dict(l=10, r=10, t=30, b=10), height=340)


def _latest_in_season() -> dict:
    d = _dt.date.today().replace(day=1)
    for _ in range(18):
        c = weekly_call(d)
        if c["in_season"]:
            return c
        d = (pd.Timestamp(d) - pd.DateOffset(months=1)).date()
    return weekly_call(_dt.date.today())


def _iso_to_date(w: str) -> pd.Timestamp:
    return pd.Timestamp.fromisocalendar(int(w[:4]), int(w.split("-W")[1]), 1)


def _chip(label: str, kind: str) -> str:
    col = {"ok": "#1a7f37", "warn": "#9a6700", "ctx": "#57606a", "gap": "#cf222e"}[kind]
    return f"<span class='chip' style='background:{col}'>{label}</span>"


def _fig_html(fig, first: bool) -> str:
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if first else False,
                       config={"displayModeBar": False})


def build() -> None:
    call = _latest_in_season()
    ut = build_uk_total()

    # 1. relay (stacked area, last 104 wks, tonnes)
    w = ut["weekly"].copy(); w["date"] = w["iso_week"].map(_iso_to_date)
    cols = [c for c in ut["origin_cols"] if c in w.columns]
    area = (w.set_index("date")[cols].clip(lower=0) / 1000)
    area = area[area.index >= area.index.max() - pd.Timedelta(weeks=104)]
    relay = px.area(area, labels={"value": "tonnes/wk", "date": "", "variable": "origin"})
    relay.update_layout(**_PLOT, legend=dict(orientation="h", y=-0.15))

    # 2. FOB history
    fob = chile_fob_weekly(); fob = fob[fob > 0]
    fob = fob[fob.index >= fob.index.max() - pd.Timedelta(weeks=170)]
    fobfig = px.line(fob, labels={"value": "FOB USD/kg", "index": "", "d": ""})
    fobfig.update_layout(**_PLOT, showlegend=False)

    # 3. producers
    pcsv = REPO_ROOT / "data" / "weekly" / "chile_uk_blueberry_by_producer.csv"
    pbar = ""
    if pcsv.exists():
        p = pd.read_csv(pcsv).sort_values("net_kg", ascending=False).head(15)
        p["t"] = p["net_kg"] / 1000
        fig = px.bar(p[::-1], x="t", y="producer", orientation="h",
                     hover_data=["top_cultivar", "top_region"],
                     labels={"t": "tonnes (cumulative)", "producer": ""})
        fig.update_layout(**{**_PLOT, "height": 420})
        pbar = _fig_html(fig, False)

    c = call
    metrics = ""
    if c["in_season"]:
        fobt = f"{c['fob_trend_pct']:+.0f}% m/m" if c["fob_trend_pct"] is not None else ""
        metrics = f"""
        <div class='cards'>
          <div class='card'><div class='big'>{c['arrivals_nowcast_t']:,.0f} t</div>
            <div class='sub'>arrivals nowcast <b>{c['anomaly_pct']:+.0f}%</b> vs normal</div></div>
          <div class='card'><div class='big'>{c['seasonal_norm_t']:,.0f} t</div>
            <div class='sub'>seasonal norm</div></div>
          <div class='card'><div class='big'>{c['supply_signal'].split()[0]}</div>
            <div class='sub'>supply signal</div></div>
          <div class='card'><div class='big'>${c['fob_usd_kg']:.2f}/kg</div>
            <div class='sub'>FOB cost (~2wk lead) {fobt}</div></div>
        </div>
        <div class='action'>ACTION: {c['action']}</div>
        <div>{_chip('supply: validated nowcast · 66% backtest · ~2wk lead','ok')}
             {_chip('FOB cost: declared, data-derived','warn')}
             {_chip('UK sell-price direction: weak, NOT a forecast','ctx')}</div>"""
    else:
        metrics = "<p>Off-season — no Chilean fruit shipping. Whole-market view below is live year-round.</p>"

    html = _TEMPLATE.format(
        landing=c["landing_month"], metrics=metrics,
        relay=_fig_html(relay, True), fob=_fig_html(fobfig, False), producers=pbar,
        live=", ".join(ut["live_lanes_available"]) or "-",
        deep=", ".join(ut["deep_sea"]),
        generated=_dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html)//1024} KB)")


_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UK Blueberry Intelligence</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f8fa;color:#1f2328}}
 .wrap{{max-width:1100px;margin:0 auto;padding:18px}}
 h1{{font-size:1.5rem;margin:.2em 0}} h2{{font-size:1.1rem;margin:1.4em 0 .4em;border-top:1px solid #d0d7de;padding-top:.8em}}
 .muted{{color:#57606a;font-size:.9rem}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}}
 .card{{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:14px 18px;flex:1;min-width:150px}}
 .big{{font-size:1.7rem;font-weight:700}} .sub{{color:#57606a;font-size:.85rem}}
 .action{{background:#dafbe1;border:1px solid #1a7f37;border-radius:8px;padding:10px 14px;margin:10px 0;font-weight:600}}
 .chip{{color:#fff;padding:2px 8px;border-radius:10px;font-size:.72rem;margin-right:6px;display:inline-block;margin-top:4px}}
 .ledger{{display:flex;gap:14px;flex-wrap:wrap}} .ledger>div{{flex:1;min-width:240px;background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:12px 16px}}
 .panel{{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:8px;margin-top:6px}}
</style></head><body><div class="wrap">
<h1>🫐 UK Blueberry Intelligence</h1>
<div class="muted">Free, self-updating (GitHub Actions). Every number wears its confidence. Generated {generated}.</div>

<h2>This week's call — Chile arrivals, landing {landing}</h2>
{metrics}

<h2>Whole-market UK supply — year-round, never blank</h2>
<div class="panel">{relay}</div>
<div class="muted">Deep-sea lanes (can lead): {deep}. Live weekly feed: {live} (others HMRC-benchmarked).</div>

<h2>Chilean FOB cost — 8-yr history (~2-week lead)</h2>
<div class="panel">{fob}</div>
<div class="muted">Declared export price (landed cost, not UK sell price). No free UK sell-side spot in the Chile season — honest gap.</div>

<h2>Who & what is landing — named producers</h2>
<div class="panel">{producers}</div>
<div class="muted">producer named ~91% of kg · region ~100% · cultivar ~46% (source ceiling) · cert GLOBALG.A.P. (inferred).</div>

<h2>Confidence ledger</h2>
<div class="ledger">
 <div><b>● Validated edge</b><br>Within-month nowcast +12% OOS, 66% directional, ~2wk lead.<br>Weekly volume reconciled to HMRC (0.1 kg). Chile↔HMRC corr 0.92.</div>
 <div><b>◐ Data-derived</b><br>FOB cost (8-yr). Named producers 91% / region 100% / cultivar 46%. Whole-market fused volume.</div>
 <div><b>⚠ Honest gaps / paid</b><br>UK sell-price direction doesn't back-test. Peru weekly + names = paid. Named certified orchard = paid CIREN / your GGNs.</div>
</div>
<div class="muted" style="margin-top:14px">5 clean negatives + 1 validated edge + 3 caught false-positives. The discipline is the product.</div>
</div></body></html>"""


if __name__ == "__main__":
    build()
