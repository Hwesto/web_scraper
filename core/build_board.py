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
# Clean short codes for export destinations (Comtrade names → readable)
DEST_CODE = {"United Kingdom": "UK", "United States": "USA", "Hong Kong": "HK",
             "United Arab Emirates": "UAE", "China": "CHN", "Germany": "GER",
             "Netherlands": "NLD", "Canada": "CAN", "South Korea": "KOR",
             "Saudi Arabia": "KSA", "Singapore": "SGP", "Malaysia": "MYS",
             "Thailand": "THA", "Japan": "JPN", "India": "IND", "Ireland": "IRL",
             "Belgium": "BEL", "Italy": "ITA", "Spain": "ESP", "Poland": "POL",
             "Sweden": "SWE", "Russia": "RUS", "Brazil": "BRA", "Argentina": "ARG",
             "Chile": "CHL", "Colombia": "COL", "Costa Rica": "CRI",
             "Ecuador": "ECU", "Israel": "ISR", "Qatar": "QAT"}


def _dcode(name: str) -> str:
    return DEST_CODE.get(name) or CODE.get(name) or str(name)[:3].upper()


# Supermarket brand colours (logo primaries)
SHOP_COLR = {"Tesco": "#00539f", "Asda": "#5fae2b", "Sainsbury's": "#f06c00",
             "Morrisons": "#00573f", "Aldi": "#1b3281", "Lidl": "#0050aa",
             "Waitrose": "#4b9560", "Ocado": "#6b2c91", "Co-op": "#00b1e7",
             "Iceland": "#cc0000", "M&S": "#1d1d1b"}


def _grams(pack: str) -> float:
    """Sort key: pack label like '150g' / '1kg' -> grams (unknown sorts last)."""
    import re
    m = re.search(r"([\d.]+)\s*(kg|g)", str(pack).lower())
    if not m:
        return 1e9
    return float(m.group(1)) * (1000 if m.group(2) == "kg" else 1)


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

    yr_ago = pd.Timestamp(cur) - pd.DateOffset(years=1)
    vc, vp, vy = vol(cur), vol(prev), vol(yr_ago)
    cc, cp = cif(cur), cif(prev)
    tot = vc.sum()
    mval = val[val["d"] == cur]["value"].sum()        # £ this month (landed/customs value)
    mavg = mval / (tot * 1000) if tot else float("nan")  # month blended landed £/kg
    rows = []
    for o in vc.sort_values(ascending=False).index:
        t = vc[o]
        if t < 1 or o not in CODE:
            continue
        pkg = cc.get(o, float("nan"))
        dpr = pkg - cp.get(o, float("nan"))
        dv = (t / vp[o] - 1) * 100 if o in vp.index and vp[o] else float("nan")
        yoy = (t / vy[o] - 1) * 100 if o in vy.index and vy[o] else float("nan")
        rows.append({"origin": o, "code": CODE[o], "t": t, "cif": pkg, "dprice": dpr,
                     "dvol": dv, "yoy": yoy, "share": t / tot * 100})
    return pd.Timestamp(cur), pd.Timestamp(prev), rows, tot, mavg, mval


def _retail(month):
    """UK shelf £/kg for the given month — ONS monthly berries proxy (year-round fallback)."""
    r = vintage.latest("ons_blueberry_retail_price").copy()
    r["d"] = pd.to_datetime(r["ref_period"])
    r = r[r["key"] == "proxy_berries_index"].sort_values("d")
    if r.empty:
        return float("nan")
    at = r[r["d"] <= month]
    return float((at if not at.empty else r).iloc[-1]["value"])


def _shelf():
    """Real blueberry shelf £/kg from the weekly Trolley multi-retailer scrape.

    Returns (week, median_standard_£/kg, [per-retailer rows]). Keys are
    `Retailer|tier|pack`; we headline on the standard tier (organic/finest are
    premium). Empty → caller falls back to the ONS proxy.
    """
    try:
        r = vintage.latest("retail_blueberry_price").copy()
    except Exception:
        return None, float("nan"), []
    if r.empty:
        return None, float("nan"), []
    r["d"] = pd.to_datetime(r["ref_period"])
    r = r[r["d"] == r["d"].max()]
    parts = r["key"].str.split("|", expand=True)
    r["retailer"], r["tier"], r["pack"] = parts[0], parts[1], parts[2]
    std = r[r["tier"] == "standard"]
    base = std if not std.empty else r
    per = []
    for ret, g in base.groupby("retailer"):
        packs = [{"pack": str(t.pack), "kg": float(t.value)}
                 for t in g.itertuples()]
        packs.sort(key=lambda p: _grams(p["pack"]))   # small -> large
        per.append({"retailer": ret, "med": float(g["value"].median()),
                    "packs": packs})
    per.sort(key=lambda x: x["med"])
    return r["d"].max(), float(base["value"].median()), per


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
    pv = float(prod["value_gbp_m"].iloc[-1]) if "value_gbp_m" in prod and not prod.empty else 0
    return {"imports_kt": l12v / 1000, "avg": avg, "ss": ss,
            "imports_gbp_m": l12val / 1e6, "uk_value_gbp_m": pv}


def _wholesale():
    """UK wholesale-market £/kg (DEFRA, weekly Jun–Nov) — the price-journey middle.
    Returns (date, £/kg) of the latest reading, or (None, nan) if unheld."""
    try:
        w = vintage.latest("defra_blueberry_price").copy()
    except Exception:
        return None, float("nan")
    if w.empty:
        return None, float("nan")
    w["d"] = pd.to_datetime(w["ref_period"]); w = w.sort_values("d")
    last = w.iloc[-1]
    return last["d"], float(last["value"])


def _reexports():
    """UK re-exports (HMRC export flows): (trailing-year kt, [(dest, kt)…])."""
    try:
        r = vintage.latest("hmrc_blueberry_reexports").copy()
    except Exception:
        return float("nan"), []
    if r.empty:
        return float("nan"), []
    r["d"] = pd.to_datetime(r["ref_period"])
    last12 = r[r["d"] >= r["d"].max() - pd.DateOffset(months=11)]
    kt = last12["value"].sum() / 1000
    top = (last12.groupby("key")["value"].sum().sort_values(ascending=False).head(3) / 1000)
    return kt, [(k, float(v)) for k, v in top.items()]


def _world():
    """Global blueberry map: (year, uk_rank, top_growers, top_exporters, top_importers).
    Trade rows are (country, value_usd, net_kg, yoy); grower rows (country, tonnes, yoy)."""
    try:
        from deep.market import comtrade_global as cg
    except Exception:
        return None, 0, [], [], []
    df = cg.load()
    if df.empty:
        return None, 0, [], [], []
    yr = int(df["year"].max())
    cur = df[df["year"] == yr]

    def tbl(role):
        prev = (df[(df["year"] == yr - 1) & (df["role"] == role)]
                .set_index("country")["value_usd"].to_dict())
        out = []
        for x in cg._table(role, 6, cur).itertuples():
            p = prev.get(x.country)
            yoy = (x.value_usd / p - 1) * 100 if p else float("nan")
            out.append((x.country, float(x.value_usd), float(x.net_kg), yoy))
        return out

    try:
        from deep.market import production as pr
        growers = pr.top_growers(6)
    except Exception:
        growers = []
    rank, _ = cg.uk_import_rank(cur)
    return yr, rank, growers, tbl("exporter"), tbl("importer")


def _ticker_html(r) -> str:
    up = r["dprice"] >= 0
    arr, cls = ("▲", "up") if up else ("▼", "down")
    tt = f"{r['t']/1000:.1f}K" if r["t"] >= 1000 else f"{r['t']:.0f}"
    yo = "" if r["yoy"] != r["yoy"] else (   # YoY volume vs same month last year
        f'<span class="chip {"up" if r["yoy"]>=0 else "down"}">'
        f'{"+" if r["yoy"]>=0 else ""}{r["yoy"]:.0f}% y/y</span>')
    return (f'<div class="tk">'
            f'<span class="sym" style="color:{COLR.get(r["origin"], "#5a3fb0")}">'
            f'<span class="code">{r["code"]}</span><span class="cty">{r["origin"]}</span></span>'
            f'<span class="vol">{tt} t</span>'
            f'<span class="shr">{r["share"]:.0f}%</span>'
            f'<span class="at">@</span><span class="px">£{r["cif"]:.2f}</span>'
            f'<span class="chg {cls}">{arr} £{abs(r["dprice"]):.2f}</span>{yo}</div>')


def _money(usd):
    """$ -> compact '$1.9bn' / '$801m'."""
    return f"${usd/1e9:.1f}bn" if usd >= 1e9 else f"${usd/1e6:.0f}m"


def build() -> str:
    cur, prev, rows, tot, mavg, mval = _board()
    relay = _relay()
    s = _summary()
    shelf_wk, shelf, per = _shelf()
    shelf_lbl = "this wk"
    if shelf != shelf:                       # no Trolley data → ONS monthly proxy
        shelf, shelf_lbl = _retail(cur), "proxy"
    when_w, whole = _wholesale()
    rex_kt, rex_top = _reexports()
    wyr, uk_rank, wgro, wexp, wimp = _world()
    cur_m = cur.month
    board = "\n".join(_ticker_html(r) for r in rows)
    # The price journey — landed (HMRC) → wholesale (DEFRA, Jun–Nov) → shelf (Trolley)
    def _step(label, val, note):
        v = f"£{val:.2f}" if val == val else "—"
        return (f'<div class="step"><span class="sl">{label}</span>'
                f'<span class="sv">{v}</span><span class="sn">{note}</span></div>')
    wnote = (pd.Timestamp(when_w).strftime("%b %Y")
             if (when_w is not None and whole == whole) else "Jun–Nov only")
    journey = ('<div class="step-arrow">→</div>'.join([
        _step("Landed", mavg, f"CIF · {MONTHS[cur.month-1]}"),
        _step("Wholesale", whole, wnote),
        _step("Shelf", shelf, shelf_lbl)]))
    # UK re-exports (HMRC export flows)
    rex = ""
    if rex_kt == rex_kt and rex_kt > 0:
        dests = ", ".join(f"{_dcode(k)} {v:.1f}kt" for k, v in rex_top)
        rex = (f'<div class="note">↩ The UK also <b>re-exports ~{rex_kt:.1f} kt/yr</b> '
               f'of fresh blueberries — mostly {dests}.</div>')
    # The world map — grow → export → import (Comtrade + FAOSTAT)
    world = ""
    if wimp or wexp or wgro:
        def _yc(yoy):
            return "" if yoy != yoy else (
                f'<span class="wy {"up" if yoy >= 0 else "down"}">'
                f'{"+" if yoy >= 0 else ""}{yoy:.0f}%</span>')

        def _trow(items):                       # trade: value + yoy + kt
            return "".join(
                f'<div class="wr"><span class="wc">{c}</span>'
                f'<span class="wv">{_money(v)}</span>{_yc(yoy)}'
                f'<span class="wk">{kg/1e6:.0f} kt</span></div>'
                for c, v, kg, yoy in items)

        def _grow(items):                       # production: tonnes + yoy
            return "".join(
                f'<div class="wr"><span class="wc">{c}</span>'
                f'<span class="wv">{t/1000:.0f} kt</span>{_yc(yoy)}</div>'
                for c, t, yoy in items)
        cols = (f'<div class="wcol"><h3>Top growers</h3>{_grow(wgro)}</div>'
                f'<div class="wcol"><h3>Top exporters</h3>{_trow(wexp)}</div>'
                f'<div class="wcol"><h3>Top importers</h3>{_trow(wimp)}</div>')
        rankline = (f"UK is the world's #{uk_rank} importer · " if uk_rank else "")
        world = (f'<h2>The world\'s blueberry map</h2>'
                 f'<p class="lede">{rankline}grow → export → import · {wyr} · '
                 f'FAOSTAT production, UN Comtrade trade</p>'
                 f'<div class="world3">{cols}</div>'
                 f'<div class="note">⚠ <b>China</b> looks small here because it grows most of '
                 f'what it eats — widely reported (IBO) as the world\'s largest producer, yet it '
                 f'reports no blueberry output to FAOSTAT and imports little, so <b>no free dataset '
                 f'captures its true scale</b>. The US is also a major grower; Netherlands, Belgium '
                 f'&amp; Hong Kong are re-export hubs.</div>')
    # On the shelf this week — real per-retailer £/kg, by pack size (Trolley)
    def _packs_html(p):
        return "".join(
            f'<span class="pk"><b class="sz">{pk["pack"]}</b> £{pk["kg"]:.2f}</span>'
            for pk in p["packs"])
    shelf_rows = "".join(
        f'<div class="shrow">'
        f'<span class="nm" style="color:{SHOP_COLR.get(p["retailer"], "#5a3fb0")}">'
        f'{p["retailer"]}</span>'
        f'<span class="packs">{_packs_html(p)}</span></div>'
        for p in per)
    shelf_when = pd.Timestamp(shelf_wk).strftime("%-d %b %Y") if shelf_wk is not None else ""
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
            d = pe[pe["player"] == p]
            d = d[~d["destination"].str.startswith(("M49-", "Other"))].head(4)
            if d.empty:
                continue
            dests = " · ".join(f'{_dcode(x.destination)} {x.pct_tonnage:.0f}%'
                               for x in d.itertuples())
            sells += (f'<div class="sell"><span class="sym" '
                      f'style="color:{COLR.get(p, "#5a3fb0")}">'
                      f'<span class="code">{CODE[p]}</span><span class="cty">{p}</span></span>'
                      f'<span class="arrow">→</span><span class="dests">{dests}</span></div>')
    world_rank = (f" &nbsp;·&nbsp; world's <b>#{uk_rank}</b> importer" if uk_rank else "")
    html = _PAGE.format(month=f"{MONTHS[cur.month-1]} {cur.year}",
                        total=f"{tot:,.0f}", mavg=f"{mavg:.2f}", spend_m=f"{mval/1e6:.0f}",
                        shelf=f"{shelf:.2f}", shelf_lbl=shelf_lbl,
                        shelf_rows=shelf_rows, shelf_when=shelf_when, journey=journey,
                        imports=f"{s['imports_kt']:.0f}", spend_yr=f"{s['imports_gbp_m']:.0f}",
                        ss=f"{s['ss']:.1f}", world_rank=world_rank, rex=rex, world=world,
                        board=board, relay=relay_cells, sells=sells,
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
 .idx .sub{{font-size:.72rem;color:#9a9082;font-weight:700;text-transform:uppercase;letter-spacing:.08em}}
 .shrow{{display:flex;align-items:baseline;gap:.5em 1.1em;flex-wrap:wrap;padding:12px 6px;
   border-bottom:1px solid var(--line)}}
 .shrow .nm{{font-size:1.5rem;font-weight:800;min-width:9ch}}
 .packs{{display:flex;flex-wrap:wrap;gap:.4em 1.1em;align-items:baseline}}
 .pk{{font-size:1.5rem;color:var(--ink);white-space:nowrap}}
 .pk .sz{{font-size:.92rem;color:#8a8070;font-weight:800;margin-right:.15em}}
 h2{{text-transform:uppercase;letter-spacing:.12em;font-size:.82rem;color:var(--accent);
   margin:34px 0 2px;font-weight:800}}
 .lede{{margin:0 0 14px;font-size:.86rem;color:#8a8070;font-weight:700}}
 .tk{{display:flex;align-items:baseline;gap:.5em 1em;flex-wrap:wrap;padding:14px 6px;
   border-bottom:1px solid var(--line)}}
 .sym{{display:inline-flex;flex-direction:column;align-self:center;min-width:4.2ch}}
 .sym .code{{font-size:2.3rem;font-weight:800;letter-spacing:-.03em;line-height:.95}}
 .sym .cty{{font-size:.62rem;font-weight:700;color:#9a9082;text-transform:uppercase;
   letter-spacing:.05em;white-space:nowrap}}
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
 .sell{{display:flex;align-items:center;gap:.7em;padding:9px 6px;border-bottom:1px solid var(--line)}}
 .sell .sym{{min-width:7ch}} .sell .sym .code{{font-size:1.5rem}} .arrow{{color:#aaa091}}
 .dests{{font-size:1.05rem;color:#5a5347;font-weight:700}}
 .journey{{display:flex;align-items:stretch;gap:6px;flex-wrap:wrap}}
 .step{{flex:1 1 0;min-width:120px;border:2px solid var(--line);border-radius:9px;
   padding:12px 14px;background:#fffefb;display:flex;flex-direction:column;gap:2px}}
 .step .sl{{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:#8a8070;font-weight:800}}
 .step .sv{{font-size:2rem;color:var(--accent)}}
 .step .sn{{font-size:.72rem;color:#9a9082;font-weight:700}}
 .step-arrow{{align-self:center;color:#bcb3a0;font-size:1.6rem;font-weight:800}}
 .note{{font-size:1rem;color:#5a5347;font-weight:700;padding:12px 4px;line-height:1.5}}
 .note b{{color:var(--accent)}}
 .world,.world3{{display:grid;grid-template-columns:1fr 1fr;gap:10px 26px}}
 .world3{{grid-template-columns:1fr 1fr 1fr}}
 .world h3{{font-size:.74rem;text-transform:uppercase;letter-spacing:.1em;color:#8a8070;
   margin:6px 0 4px;font-weight:800}}
 .wr{{display:flex;align-items:baseline;gap:.35em .5em;flex-wrap:wrap;padding:6px 2px;
   border-bottom:1px solid var(--line)}}
 .wr .wc{{flex:1 1 100%;font-size:.92rem;font-weight:800;color:var(--ink)}}
 .wr .wv{{font-size:1.05rem;color:var(--accent);font-weight:800}}
 .wr .wy{{font-size:.72rem;font-weight:800}}
 .wr .wk{{font-size:.78rem;color:#9a9082;margin-left:auto}}
 @media(max-width:560px){{.world,.world3{{grid-template-columns:1fr}}}}
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
<div class="idx">{month} &nbsp;·&nbsp; <b>{total} t</b> landed (<b>£{spend_m}m</b>) &nbsp;·&nbsp;
UK-grown <b>{ss}%</b> &nbsp;·&nbsp; <b>{imports}K t</b> / <b>£{spend_yr}m</b> a year{world_rank}</div>

<h2>Who's landing this month</h2>
<p class="lede">tonnes · share · landed £/kg · ▲▼ vs last month · y/y volume</p>
{board}

<h2>The price journey</h2>
<p class="lede">per kilo at each stage · latest reading (dates differ)</p>
<div class="journey">{journey}</div>

<h2>On the shelf this week</h2>
<p class="lede">£/kg by retailer · {shelf_when}</p>
{shelf_rows}

<h2>The relay</h2>
<p class="lede">who leads UK supply each month</p>
<div class="relay">{relay}</div>

<h2>Where each player else ships</h2>
<p class="lede">2024 · % of their tonnage</p>
{sells}
{rex}

{world}

<div class="foot">Free data: HMRC OTS (monthly imports + re-exports, ~6-wk lag) · UN Comtrade
(global trade + destinations) · DEFRA (UK production + wholesale price) · Trolley (multi-retailer shelf, weekly).
Auto-updates weekly · <a href="deep.html">full editorial view →</a> ·
generated {generated}.</div>
</div></body></html>"""


if __name__ == "__main__":
    build()
    print(f"wrote {OUT}")
