"""Britain's Blueberry Board — a stock-ticker view of the UK fresh-blueberry market.

At-a-glance MONTHLY: one ticker per origin (HMRC) — SYMBOL · tonnes · @ CIF £/kg ·
▲▼ price move vs prior month · volume %Δ chip. Plus the relay (who leads each month)
and where each major player else ships (Comtrade annual). Pure HTML/CSS, GitHub Pages.
Reads only committed data. Run: python -m core.build_board
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

from deep.config import REPO_ROOT
from deep.store import vintage
from core import player_exports, uk_production

OUT = REPO_ROOT / "docs" / "index.html"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CODE = {"Peru": "PER", "Morocco": "MAR", "South Africa": "ZAF", "Chile": "CHL",
        "Spain": "ESP", "Netherlands": "NLD", "Poland": "POL", "Portugal": "PRT",
        "United States": "USA", "Argentina": "ARG"}
COLR = {"Peru": "#4c5fd5", "Morocco": "#e8833a", "South Africa": "#2a9d8f",
        "Chile": "#6b3fa0", "Spain": "#c9a227", "Netherlands": "#7a8699",
        "Poland": "#b1543a", "Portugal": "#3a8f6b"}


def _months(v):
    return sorted(v["d"].unique())


def _board():
    v = vintage.latest("hmrc_blueberry_imports").copy(); v["d"] = pd.to_datetime(v["ref_period"])
    val = vintage.latest("hmrc_blueberry_import_value").copy(); val["d"] = pd.to_datetime(val["ref_period"])
    # Use the latest *complete* month: HMRC OTS lands ~6 wks late and the most
    # recent month is usually a partial first-estimate. Treat a month as settled
    # once it is ≥70 days old; fall back to raw tail if we don't have two settled.
    ms = _months(v)
    today = pd.Timestamp(_dt.date.today())
    complete = [m for m in ms if (today - pd.Timestamp(m)).days >= 70]
    use = complete if len(complete) >= 2 else ms
    cur, prev = use[-1], use[-2]

    def vol(d): return v[v["d"] == d].groupby("key")["value"].sum()
    def cif(d):
        a = v[v["d"] == d].groupby("key")["value"].sum()
        b = val[val["d"] == d].groupby("key")["value"].sum()
        return b / (a * 1000)

    vc, vp, cc, cp = vol(cur), vol(prev), cif(cur), cif(prev)
    tot = vc.sum()
    mval = val[val["d"] == cur]["value"].sum()
    mavg = mval / (tot * 1000) if tot else float("nan")  # month blended landed £/kg
    rows = []
    for o in vc.sort_values(ascending=False).index:
        t = vc[o]
        if t < 1 or o not in CODE:
            continue
        pkg = cc.get(o, float("nan"))
        dpr = pkg - cp.get(o, float("nan"))
        dv = (t / vp[o] - 1) * 100 if o in vp.index and vp[o] else float("nan")
        rows.append({"origin": o, "code": CODE[o], "t": t, "cif": pkg,
                     "dprice": dpr, "dvol": dv, "share": t / tot * 100})
    return pd.Timestamp(cur), pd.Timestamp(prev), rows, tot, mavg


def _retail(month):
    """UK shelf £/kg for the given month — ONS monthly berries proxy (year-round)."""
    r = vintage.latest("ons_blueberry_retail_price").copy()
    r["d"] = pd.to_datetime(r["ref_period"])
    r = r[r["key"] == "proxy_berries_index"].sort_values("d")
    if r.empty:
        return float("nan")
    at = r[r["d"] <= month]
    return float((at if not at.empty else r).iloc[-1]["value"])


def _relay(v=None):
    v = v or vintage.latest("hmrc_blueberry_imports").copy()
    v["d"] = pd.to_datetime(v["ref_period"]); v["m"] = v["d"].dt.month
    recent = v[v["d"] >= v["d"].max() - pd.DateOffset(months=60)]
    lead = (recent.groupby(["m", "key"])["value"].sum().reset_index()
            .sort_values("value").groupby("m").tail(1).set_index("m")["key"])
    return [lead.get(m, "") for m in range(1, 13)]


def _summary():
    v = vintage.latest("hmrc_blueberry_imports").copy(); v["d"] = pd.to_datetime(v["ref_period"])
    val = vintage.latest("hmrc_blueberry_import_value").copy(); val["d"] = pd.to_datetime(val["ref_period"])
    l12v = v[v["d"] >= v["d"].max() - pd.DateOffset(months=11)]["value"].sum()
    l12val = val[val["d"] >= val["d"].max() - pd.DateOffset(months=11)]["value"].sum()
    avg = l12val / (l12v * 1000)
    prod = uk_production.load()
    pk = float(prod["production_kt"].iloc[-1]) if not prod.empty else 0
    ss = pk / (l12v / 1000 + pk) * 100 if l12v else 0
    return {"imports_kt": l12v / 1000, "avg": avg, "ss": ss}


def _ticker_html(r) -> str:
    up = r["dprice"] >= 0
    arr, cls = ("▲", "up") if up else ("▼", "down")
    tt = f"{r['t']/1000:.1f}K" if r["t"] >= 1000 else f"{r['t']:.0f}"
    dv = "" if r["dvol"] != r["dvol"] else (
        f'<span class="chip {"up" if r["dvol"]>=0 else "down"}">'
        f'{"+" if r["dvol"]>=0 else ""}{r["dvol"]:.0f}% vol</span>')
    dim = "" if r["share"] >= 5 else " dim"
    return (f'<div class="tk{dim}">'
            f'<span class="sym" style="color:{COLR.get(r["origin"], "#5a3fb0")}">{r["code"]}</span>'
            f'<span class="vol">{tt} t</span>'
            f'<span class="shr">{r["share"]:.0f}%</span>'
            f'<span class="at">@</span><span class="px">£{r["cif"]:.2f}</span>'
            f'<span class="chg {cls}">{arr} £{abs(r["dprice"]):.2f}</span>{dv}</div>')


def build() -> str:
    cur, prev, rows, tot, mavg = _board()
    relay = _relay()
    s = _summary()
    retail = _retail(cur)
    cur_m = cur.month
    board = "\n".join(_ticker_html(r) for r in rows)
    relay_cells = "".join(
        f'<div class="rc{" now" if m == cur_m else ""}" '
        f'style="border-color:{COLR.get(relay[m-1], "#ccc")}">'
        f'<b>{MONTHS[m-1]}</b><span style="color:{COLR.get(relay[m-1], "#888")}">'
        f'{CODE.get(relay[m-1], "·")}</span></div>'
        for m in range(1, 13))
    # View 2 — where each player sells (annual)
    pe = player_exports.load()
    sells = ""
    if not pe.empty:
        for p in ["Peru", "Chile", "Morocco", "South Africa", "Spain", "Netherlands"]:
            d = pe[pe["player"] == p].head(4)
            if d.empty:
                continue
            dests = " · ".join(f'{CODE.get(x.destination, x.destination[:3].upper())} '
                               f'{x.pct_tonnage:.0f}%' for x in d.itertuples())
            sells += (f'<div class="sell"><span class="sym" '
                      f'style="color:{COLR.get(p, "#5a3fb0")}">{CODE[p]}</span>'
                      f'<span class="arrow">→</span><span class="dests">{dests}</span></div>')
    # Country-code legend — every code shown on the page, in trade-rank order
    names = {r["origin"] for r in rows} | {x for x in relay if x}
    if not pe.empty:
        names |= set(pe["player"].unique())
    legend = " &nbsp;·&nbsp; ".join(
        f'<span><span class="sw" style="background:{COLR.get(n, "#5a3fb0")}"></span>'
        f'<b>{CODE.get(n, n[:3].upper())}</b> {n}</span>'
        for n in CODE if n in names)
    html = _PAGE.format(month=f"{MONTHS[cur.month-1]} {cur.year}",
                        total=f"{tot:,.0f}", mavg=f"{mavg:.2f}", retail=f"{retail:.2f}",
                        imports=f"{s['imports_kt']:.0f}", ss=f"{s['ss']:.1f}",
                        board=board, relay=relay_cells, sells=sells, legend=legend,
                        generated=_dt.date.today().isoformat())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    return html


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Britain's Blueberry Board</title>
<style>
 :root{{--ink:#2a2622;--accent:#5a3fb0;--up:#1a8a3c;--down:#c0392b;--line:#dcd4c4}}
 *{{box-sizing:border-box}}
 body{{margin:0;color:var(--ink);background:#ece6d8;
   background-image:linear-gradient(#e2dac9 1px,transparent 1px),linear-gradient(90deg,#e2dac9 1px,transparent 1px);
   background-size:24px 24px;
   font-family:"Helvetica Neue",Arial,sans-serif;font-weight:700;font-stretch:condensed}}
 .wrap{{max-width:840px;margin:0 auto;padding:34px 20px 60px}}
 .masthead{{display:flex;align-items:center;justify-content:space-between;gap:18px}}
 .head{{min-width:0}}
 .hero{{width:184px;height:auto;flex:none;filter:drop-shadow(0 6px 14px rgba(42,38,34,.22))}}
 .kick{{text-transform:uppercase;letter-spacing:.2em;font-size:.72rem;color:var(--accent);font-weight:800}}
 h1{{font-size:2.6rem;margin:.1em 0 .05em;letter-spacing:-.02em;color:var(--ink)}}
 .idx{{font-size:1rem;color:#6a6052;border-top:2px solid var(--line);border-bottom:2px solid var(--line);
   padding:10px 0;margin:14px 0 26px;font-weight:700}}
 .idx b{{color:var(--accent)}}
 h2{{text-transform:uppercase;letter-spacing:.12em;font-size:.82rem;color:#8a8070;
   margin:34px 0 12px;font-weight:800}}
 .tk{{display:flex;align-items:baseline;gap:.5em 1em;flex-wrap:wrap;padding:14px 6px;
   border-bottom:1px solid var(--line)}}
 .tk.dim{{opacity:.42}}
 .sym{{font-size:2.3rem;font-weight:800;letter-spacing:-.03em;min-width:3.4ch}}
 .vol{{font-size:1.5rem;color:#5a5347}}
 .shr{{font-size:1.05rem;color:#8a8070;font-weight:800}}
 .at{{color:#aaa091;font-size:1.2rem}}
 .px{{font-size:2.1rem;color:var(--ink)}}
 .chg{{font-size:1.6rem}} .up{{color:var(--up)}} .down{{color:var(--down)}}
 .chip{{font-size:.78rem;padding:2px 8px;border-radius:20px;font-weight:800;align-self:center;
   background:#fff8}} .chip.up{{color:var(--up)}} .chip.down{{color:var(--down)}}
 .relay{{display:grid;grid-template-columns:repeat(12,1fr);gap:5px}}
 .rc{{border:2px solid var(--line);border-radius:7px;padding:8px 2px;text-align:center;
   background:#fffefb}}
 .rc b{{display:block;font-size:.66rem;color:#9a9082;letter-spacing:.05em}}
 .rc span{{font-size:.92rem;font-weight:800}}
 .rc.now{{box-shadow:0 0 0 2px var(--accent) inset;background:#fff}}
 .sell{{display:flex;align-items:baseline;gap:.7em;padding:9px 6px;border-bottom:1px solid var(--line)}}
 .sell .sym{{font-size:1.5rem;min-width:3.4ch}} .arrow{{color:#aaa091}}
 .dests{{font-size:1.05rem;color:#5a5347;font-weight:700}}
 .legend{{margin-top:18px;font-size:.9rem;color:#6a6052;font-weight:700;line-height:1.9}}
 .legend b{{color:var(--ink);font-weight:800}}
 .legend .sw{{display:inline-block;width:.72em;height:.72em;border-radius:50%;margin-right:.35em;
   vertical-align:middle}}
 .foot{{margin-top:40px;border-top:2px solid var(--line);padding-top:16px;font-size:.78rem;
   color:#8a8070;font-weight:700}}
 .foot a{{color:var(--accent)}}
 @media(max-width:560px){{h1{{font-size:2rem}}.sym{{font-size:1.8rem}}.px{{font-size:1.6rem}}
   .relay{{grid-template-columns:repeat(6,1fr)}}.hero{{width:112px}}}}
</style></head><body><div class="wrap">
<div class="masthead">
 <div class="head">
  <div class="kick">🫐 the UK fresh-blueberry market</div>
  <h1>Britain's Blueberry Board</h1>
 </div>
 <img class="hero" src="hero.png" alt="A British blueberry in a navy suit and Union-Jack tie">
</div>
<div class="idx">{month} &nbsp;·&nbsp; <b>{total} t</b> landed this month &nbsp;·&nbsp;
landed <b>£{mavg}/kg</b> &rarr; shelf <b>£{retail}/kg</b> &nbsp;·&nbsp;
UK-grown <b>{ss}%</b> &nbsp;·&nbsp; {imports}K t/yr</div>

<h2>Who's landing this month — tonnes · share @ landed £/kg, vs last month</h2>
{board}

<h2>The relay — who leads each month</h2>
<div class="relay">{relay}</div>

<h2>Where each player else ships (2024 · % of their tonnage)</h2>
{sells}

<h2>Country codes</h2>
<div class="legend">{legend}</div>

<div class="foot">Free data: HMRC OTS (monthly imports, ~6-wk lag) · UN Comtrade
(annual destinations) · DEFRA Horticulture (UK production) · ONS (shelf price, berries proxy).
Auto-updates weekly · <a href="deep.html">full editorial view →</a> ·
generated {generated}.</div>
</div></body></html>"""


if __name__ == "__main__":
    build()
    print(f"wrote {OUT}")
