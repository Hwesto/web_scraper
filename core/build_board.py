"""Britain's Blueberry Board — a stock-ticker view of the UK fresh-blueberry market.

At-a-glance MONTHLY: one ticker per origin (HMRC) — SYMBOL · tonnes · share · landed
CIF £/kg · ▲▼ vs last month · y/y volume chip (material lanes only). Plus the price
journey (12-mo blend landed → shelf), the relay (who leads each month), where each
origin sends its fruit, the world map (grow→export→import) and the domestic market.
Pure HTML/CSS, GitHub Pages. Reads only committed data. Run: python -m core.build_board
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
             "Ecuador": "ECU", "Israel": "ISR", "Qatar": "QAT", "France": "FRA",
             "Mexico": "MEX", "Switzerland": "CHE", "Denmark": "DNK", "Norway": "NOR",
             "Austria": "AUT", "Portugal": "PRT", "Vietnam": "VNM", "Indonesia": "IDN"}

# Ticker materiality floors — below these a £/kg or a y/y move is a customs
# rounding artefact (single consignment), not a signal.
PRICE_FLOOR_SHARE = 0.5   # % of the month: suppress @£/kg + ▲▼ below this
YOY_MIN_SHARE = 3.0       # % of the month  } both required for a y/y chip
YOY_MIN_T = 500           # tonnes          } (kills big % on tiny bases)

# --- Price build-up: literature margin/shrink assumptions (sourced; all ESTIMATES) ---
# Used only to DECOMPOSE the measured border→shelf spread, never to invent a price.
RETAIL_GROSS_MARGIN = 0.308   # realized produce-dept gross margin — NGA / Nutrition
#                               Incentive Hub, "Retail Grocery Pricing: A Primer" (2020)
FRESH_FRUIT_SHRINK = 0.126    # fresh-fruit retail shrink by weight — USDA ERS,
#                               Buzby et al. EIB-155 (2016); soft berries run higher
RETAIL_NET_MARGIN = 0.017     # food-retail net profit margin — FMI, Food Retailing
#                               Industry Speaks (2024); berries often a loss-leader
#                               (Richards & Hamilton, AJAE 88(3), 2006)
# Net fruit per 40-ft reefer. Blueberries are volume/airflow-limited (clamshells +
# ventilation gaps), so well under the ~26 t weight cap: ~20 pallets/40-ft reefer
# (ICE Transport / FreightAmigo logistics specs, "20–25 pallets") × ~1 t per export
# pallet ≈ ~20 t. Industry approximation — varies with punnet size & packout.
CONTAINER_TONNES = 20


def _cost_buildup(landed, shelf):
    """Decompose a measured shelf £/kg into border cost + UK import/distribution +
    retailer gross margin, using the NGA produce-margin benchmark. The two ends are
    MEASURED (HMRC landed, Trolley shelf); the split is modelled. Returns
    [(label, £/kg, pct_of_shelf, source, css)] or None, plus a loss-leader flag.
    """
    if not (landed == landed and shelf == shelf and shelf > 0 and landed > 0):
        return None, False
    into_store = shelf * (1 - RETAIL_GROSS_MARGIN)     # retailer buy-in implied by GM
    importer = into_store - landed                     # residual: import + distribution
    retail = shelf - into_store                        # = shelf × GM
    # Squeeze: the border→shelf spread can't even cover landed + a benchmark retail
    # margin, so the retailer is selling near break-even (the loss-leader case).
    loss_leader = importer < 0
    if loss_leader:
        importer, retail = 0.0, shelf - landed
    segs = [
        ("Border — landed CIF", landed, landed / shelf * 100, "HMRC · measured", "border"),
        ("UK import & distribution", importer, importer / shelf * 100, "implied remainder", "dist"),
        ("Retailer gross margin", retail, retail / shelf * 100,
         f"NGA {RETAIL_GROSS_MARGIN*100:.1f}%", "retail"),
    ]
    return segs, loss_leader


def _dcode(name: str) -> str:
    code = DEST_CODE.get(name) or CODE.get(name)
    if code:
        return code
    print(f"[build_board] WARN: no DEST_CODE for {name!r}; using {name[:3].upper()}")
    return str(name)[:3].upper()


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


# The origins that actually supply the UK in volume — the strip stays legible and
# avoids tiny-lane unit-value artefacts (e.g. a few hundred kg of US fruit @ £2/kg).
INSEASON_ORIGINS = ["Chile", "Peru", "Morocco", "Spain", "Netherlands", "South Africa"]


def _inseason_cif(years=3, frac=0.25, min_t=2000):
    """Per-origin volume-weighted CIF £/kg over each origin's *in-season* months
    (months where it moves ≥`frac` of its own peak month), last `years` years,
    for the major UK-supply origins carrying ≥`min_t` tonnes in that window.
    Returns [(origin, £/kg)] cheapest→dearest — the counter-season workhorse
    prices a single thin month (April) never reveals.
    """
    v = vintage.latest("hmrc_blueberry_imports").copy(); v["d"] = pd.to_datetime(v["ref_period"])
    val = vintage.latest("hmrc_blueberry_import_value").copy(); val["d"] = pd.to_datetime(val["ref_period"])
    cut = v["d"].max() - pd.DateOffset(years=years)
    v, val = v[v["d"] >= cut], val[val["d"] >= cut]
    out = []
    for o in INSEASON_ORIGINS:
        vo = v[v["key"] == o]
        by_m = vo.groupby("d")["value"].sum()
        if by_m.empty or by_m.max() <= 0:
            continue
        months = by_m[by_m >= frac * by_m.max()].index
        kg = vo[vo["d"].isin(months)]["value"].sum()
        gbp = val[(val["key"] == o) & (val["d"].isin(months))]["value"].sum()
        if kg > min_t:                                # real volume → trustworthy price
            out.append((o, gbp / (kg * 1000)))
    return sorted(out, key=lambda x: x[1])


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

    Returns (week, headline_£/kg, [per-retailer rows], n_packs). Keys are
    `Retailer|tier|pack`; we use the standard tier (organic/finest are premium).
    The headline is PACK-NORMALISED — the median across retailers of each
    retailer's *largest* pack — because small punnets (150g) carry a much higher
    £/kg and would inflate a naive all-pack median. Empty → caller uses the proxy.
    """
    try:
        r = vintage.latest("retail_blueberry_price").copy()
    except Exception:
        return None, float("nan"), [], 0
    if r.empty:
        return None, float("nan"), [], 0
    r["d"] = pd.to_datetime(r["ref_period"])
    r = r[r["d"] == r["d"].max()]
    parts = r["key"].str.split("|", expand=True)
    r["retailer"], r["tier"], r["pack"] = parts[0], parts[1], parts[2]
    per, big = [], []
    for ret, g in r.groupby("retailer"):              # all tiers: standard + finest/organic
        packs = [{"pack": str(t.pack), "kg": float(t.value), "tier": str(t.tier)}
                 for t in g.itertuples()]
        # standard first (by size), then variants (by size)
        packs.sort(key=lambda p: (p["tier"] != "standard", _grams(p["pack"])))
        std = [p for p in packs if p["tier"] == "standard"]
        med_src = std or packs
        if std:
            big.append(std[-1]["kg"])                 # largest STANDARD pack's £/kg
        per.append({"retailer": ret,
                    "med": float(pd.Series([p["kg"] for p in med_src]).median()),
                    "packs": packs})
    per.sort(key=lambda x: x["med"])
    headline = float(pd.Series(big).median()) if big else float("nan")
    return r["d"].max(), headline, per, int(len(r))


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


def _consumption():
    """Apparent domestic consumption = production + imports − exports, by market.
    Returns (year, [(country, cons_kt, selfgrown_pct, prod_source_or_None)]).
    Production = FAOSTAT + sourced overrides (China) + DEFRA for the UK."""
    try:
        from deep.market import comtrade_global as cg, production as pr
    except Exception:
        return None, []
    tr = cg.load()
    if tr.empty:
        return None, []
    yr = int(tr["year"].max())
    cur = tr[tr["year"] == yr]
    imp = cur[cur["role"] == "importer"].set_index("country")["net_kg"].div(1e6).to_dict()
    exp = cur[cur["role"] == "exporter"].set_index("country")["net_kg"].div(1e6).to_dict()
    prod = pr.production_by_country()                 # {country: (tonnes, yr, src)}
    try:                                              # UK absent from FAOSTAT → DEFRA
        ukp = uk_production.load()
        if not ukp.empty and "United Kingdom" not in prod:
            prod["United Kingdom"] = (float(ukp["production_kt"].iloc[-1]) * 1000, yr, "DEFRA")
    except Exception:
        pass
    rows = []
    for c in set(prod) | set(imp) | set(exp):
        P = prod.get(c, (0.0, yr, None))[0] / 1000    # kt
        src = prod.get(c, (0.0, yr, None))[2]
        cons = P + imp.get(c, 0.0) - exp.get(c, 0.0)
        if cons <= 0:
            continue
        ss = P / cons * 100 if cons > 0 else float("nan")   # uncapped: >100% = net exporter
        rows.append((c, cons, ss, src))
    rows.sort(key=lambda r: -r[1])
    return yr, rows[:7]


def _delta_chip(val, unit, cls_set=("up", "down", "flat")):
    """A coloured ▲/▼/▬ chip with a value, neutral when essentially flat."""
    up, down, flat = cls_set
    cls = flat if abs(val) < 0.5 else (up if val > 0 else down)
    arr = "▬" if cls == flat else ("▲" if val > 0 else "▼")
    return cls, arr


def _ticker_html(r) -> str:
    tt = f"{r['t']/1000:.1f}K" if r["t"] >= 1000 else f"{r['t']:.0f}"
    shr = f'{r["share"]:.0f}%' if r["share"] >= 1 else "<1%"
    # @£/kg + ▲▼ only when the lane carries enough volume to trust the unit value
    if r["share"] >= PRICE_FLOOR_SHARE and r["cif"] == r["cif"]:
        cls, arr = _delta_chip(r["dprice"], "")
        price = (f'<span class="at">@</span><span class="px">£{r["cif"]:.2f}</span>'
                 f'<span class="chg {cls}">{arr} £{abs(r["dprice"]):.2f}</span>')
    else:
        price = '<span class="small-lane">small lane — no reliable price</span>'
    # y/y volume chip: only on a material base; cap tiny-base blow-ups
    yo = ""
    if r["yoy"] == r["yoy"] and r["share"] >= YOY_MIN_SHARE and r["t"] >= YOY_MIN_T:
        y = r["yoy"]
        cls, arr = _delta_chip(y, "")
        lbl = ("±0%" if cls == "flat" else ">+100%" if y >= 100
               else "<-100%" if y <= -100 else f'{"+" if y >= 0 else ""}{y:.0f}%')
        yo = f'<span class="chip {cls}">{arr} {lbl} y/y</span>'
    return (f'<div class="tk">'
            f'<span class="sym" style="color:{COLR.get(r["origin"], "#5a3fb0")}">'
            f'<span class="code">{r["code"]}</span><span class="cty">{r["origin"]}</span></span>'
            f'<span class="vol">{tt} t</span>'
            f'<span class="shr">{shr}</span>'
            f'{price}{yo}</div>')


def _money(usd):
    """$ -> compact '$1.9bn' / '$801m'."""
    return f"${usd/1e9:.1f}bn" if usd >= 1e9 else f"${usd/1e6:.0f}m"


def build() -> str:
    cur, prev, rows, tot, mavg, mval = _board()
    relay = _relay()
    s = _summary()
    landed = s["avg"]                        # 12-mo volume-weighted blended CIF £/kg
    shelf_wk, shelf, per, n_packs = _shelf()
    shelf_lbl = f"wk {pd.Timestamp(shelf_wk).strftime('%-d %b')}" if shelf_wk is not None else "this wk"
    if shelf != shelf:                       # no Trolley data → ONS monthly proxy
        shelf, shelf_lbl = _retail(cur), "ONS proxy"
    when_w, whole = _wholesale()
    rex_kt, rex_top = _reexports()
    wyr, uk_rank, wgro, wexp, wimp = _world()
    cur_m = cur.month
    lag_wks = int((pd.Timestamp(_dt.date.today()) - cur).days / 7)
    board = "\n".join(_ticker_html(r) for r in rows)
    # The price journey — a cost build-up of the measured shelf £/kg: the all-origin
    # LANDED import CIF (12-mo volume-weighted) and the supermarket SHELF (pack-
    # normalised) are MEASURED; the split between them (UK import/distribution vs
    # retailer gross margin) is MODELLED off the NGA produce-margin benchmark.
    # DEFRA wholesale stays an aside (British-season home-grown spot, not a step).
    markup = (f'+{(shelf/landed - 1)*100:.0f}%'
              if (landed == landed and landed > 0 and shelf == shelf) else '')
    segs, loss_leader = _cost_buildup(landed, shelf)
    if segs:
        bar = "".join(f'<i class="seg {css}" style="width:{pct:.1f}%" '
                      f'title="{lbl}: £{v:.2f} ({pct:.0f}%)"></i>'
                      for lbl, v, pct, src, css in segs)
        legend = "".join(
            f'<div class="bl"><span class="dot {css}"></span>'
            f'<span class="blk">{lbl}</span><span class="blv">£{v:.2f}</span>'
            f'<span class="blp">{pct:.0f}%</span><span class="bls">{src}</span></div>'
            for lbl, v, pct, src, css in segs)
        ll = (' At this blend the spread barely covers a normal retail margin — '
              'consistent with berries sold near break-even.' if loss_leader else '')
        econ = (f'<div class="note">That ~{RETAIL_GROSS_MARGIN*100:.0f}% retail slice is gross, '
                f'not profit: fresh fruit loses <b>{FRESH_FRUIT_SHRINK*100:.0f}%+</b> by weight to '
                f'shrink (USDA ERS, 2016) — soft berries more — so the initial markup is set ~40–50% '
                f'to net it down; food-retail <b>net</b> margin is only ~<b>{RETAIL_NET_MARGIN*100:.1f}%</b> '
                f'(FMI, 2024), and berries are often run as a deliberate <b>loss-leader</b> in peak '
                f'season (Richards &amp; Hamilton, 2006).{ll} Border &amp; shelf measured; split modelled.</div>')
        journey = (f'<div class="bbar">{bar}</div>'
                   f'<div class="bends"><span>£{landed:.2f} landed</span>'
                   f'<span>{markup}</span><span>£{shelf:.2f} shelf</span></div>'
                   f'<div class="bcont">A <b>40-ft reefer (~{CONTAINER_TONNES} t)</b> lands at '
                   f'~<b>£{landed*CONTAINER_TONNES:.0f}k</b> and rings up at '
                   f'~<b>£{shelf*CONTAINER_TONNES:.0f}k</b> on shelf '
                   f'<span class="src">~20 pallets × ~1 t · ICE Transport / industry, packout-dependent</span></div>'
                   f'<div class="blegend">{legend}</div>{econ}')
    else:
        journey = f'<div class="note">Landed £{landed:.2f}/kg → shelf £{shelf:.2f}/kg.</div>'
    # In-season per-origin landed prices — the cheap counter-season workhorses a
    # single shoulder month hides (Chile is out of season in April and never shows).
    insn = _inseason_cif()
    strip = ""
    if insn:
        chips = " · ".join(
            f'<span style="color:{COLR.get(o, "#5a3fb0")}"><b>{CODE.get(o, o[:3].upper())}</b> £{c:.2f}</span>'
            for o, c in insn)
        strip = (f'<div class="strip"><span class="sl">In season, landed £/kg</span>{chips}</div>')
    whole_note = ""
    if whole == whole and when_w is not None:
        whole_note = (f'<div class="aside"><span class="tag">not a journey step</span> '
                      f'UK-grown, British-season <b>wholesale</b> (DEFRA · New Covent Garden) is '
                      f'<b>£{whole:.2f}/kg</b> ({pd.Timestamp(when_w).strftime("%b %Y")}) — premium '
                      f'loose fruit sold spot, a different product/season to imported retail, so it '
                      f'sits above both prices above.</div>')
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
            if yoy != yoy:
                return ""
            cls, arr = _delta_chip(yoy, "")
            lbl = ("±0%" if cls == "flat" else ">+100%" if yoy >= 100
                   else f'{"+" if yoy >= 0 else ""}{yoy:.0f}%')
            return f'<span class="wy {cls}">{arr} {lbl}</span>'

        def _trow(items):                       # trade: $ value + yoy(value) + kt
            return "".join(
                f'<div class="wr"><span class="wc">{c}{"†" if c == "China" else ""}</span>'
                f'<span class="wv">{_money(v)}</span>{_yc(yoy)}'
                f'<span class="wk">{kg/1e6:.0f} kt</span></div>'
                for c, v, kg, yoy in items)

        def _grow(items):                       # production: tonnes + yoy(tonnage)
            return "".join(
                f'<div class="wr"><span class="wc">{c}</span>'
                f'<span class="wv">{t/1000:.0f} kt</span>{_yc(yoy)}</div>'
                for c, t, yoy in items)
        cols = (f'<div class="wcol"><h3>Top growers</h3>'
                f'<div class="wsub">production · kt · y/y tonnage</div>{_grow(wgro)}</div>'
                f'<div class="wcol"><h3>Top exporters</h3>'
                f'<div class="wsub">trade value · $ · y/y value · kt volume</div>{_trow(wexp)}</div>'
                f'<div class="wcol"><h3>Top importers</h3>'
                f'<div class="wsub">trade value · $ · y/y value · kt volume</div>{_trow(wimp)}</div>')
        rankline = (f"UK is the world's #{uk_rank} importer · " if uk_rank else "")
        world = (f'<h2>The world\'s blueberry map</h2>'
                 f'<p class="lede">{rankline}grow → export → import · {wyr} · '
                 f'FAOSTAT production, UN Comtrade trade</p>'
                 f'<div class="note">† <b>China</b> looks small here but grows most of what it eats — '
                 f'reported (IBO) as the world\'s largest producer, yet it reports no output to FAOSTAT '
                 f'and imports little, so <b>no free dataset captures its true scale</b>. '
                 f'Netherlands, Belgium &amp; Hong Kong are re-export hubs (high trade, low home demand).</div>'
                 f'<div class="world3">{cols}</div>')
    # Domestic market — apparent consumption (production + imports − exports)
    cyr, crows = _consumption()
    market = ""
    if crows:
        flagged = any(r[3] and r[3] != "DEFRA" for r in crows)
        mr = ""
        for c, cons, ss, src in crows:
            star = "†" if (src and src != "DEFRA") else ""
            if ss > 105:                               # produces more than it eats
                label = f'net exporter · grows {ss/100:.1f}× what it eats'
                bar = '<span class="mbar exp"><i style="width:100%"></i></span>'
            else:
                label = f'{ss:.0f}% home-grown'
                bar = f'<span class="mbar"><i style="width:{min(ss,100):.0f}%"></i></span>'
            mr += (f'<div class="mr"><span class="mc">{c}{star}</span>'
                   f'<span class="mv">{cons:,.0f} kt</span>{bar}'
                   f'<span class="ms">{label}</span></div>')
        foot = ('<div class="note">† <b>China</b> production is a sourced industry estimate '
                '(Produce Report / IBO, ~525 kt 2023) — it reports none to FAOSTAT; '
                'all other production is FAOSTAT (UK: DEFRA).</div>' if flagged else "")
        market = (f'<h2>Domestic market — who actually eats it</h2>'
                  f'<p class="lede">apparent consumption = production + imports − exports · {cyr}'
                  f' · de-hubs the re-exporters</p>{mr}{foot}')
    # On the shelf this week — real per-retailer £/kg, by pack size (Trolley)
    def _packs_html(p):
        out = ""
        for pk in p["packs"]:
            badge = "" if pk["tier"] == "standard" else f'<span class="tier">{pk["tier"]}</span>'
            out += f'<span class="pk"><b class="sz">{pk["pack"]}</b> £{pk["kg"]:.2f}{badge}</span>'
        return out
    shelf_rows = "".join(
        f'<div class="shrow">'
        f'<span class="nm" style="color:{SHOP_COLR.get(p["retailer"], "#5a3fb0")}">'
        f'{p["retailer"]}</span>'
        f'<span class="packs">{_packs_html(p)}</span></div>'
        for p in per)
    shelf_when = pd.Timestamp(shelf_wk).strftime("%-d %b %Y") if shelf_wk is not None else ""
    shelf_lede = (f"{len(per)} of 11 retailers · {n_packs} packs · w/c {shelf_when} · "
                  f"£/kg = pack price ÷ weight, so small punnets read dearer")
    now_m = pd.Timestamp(_dt.date.today()).month
    relay_cells = "".join(
        f'<div class="rc{" now" if m == now_m else ""}" title="{relay[m-1] or "—"}" '
        f'style="border-color:{COLR.get(relay[m-1], "#ccc")}">'
        f'<b>{MONTHS[m-1]}</b><span style="color:{COLR.get(relay[m-1], "#888")}">'
        f'{CODE.get(relay[m-1], "·")}</span>'
        f'{"<i>now</i>" if m == now_m else ""}</div>'
        for m in range(1, 13))
    relay_legend = " · ".join(
        f'<b style="color:{COLR.get(o, "#5a3fb0")}">{CODE.get(o, o[:3].upper())}</b> {o}'
        for o in dict.fromkeys(relay) if o)
    # View 2 — where each origin sends its fruit (annual)
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
    html = _PAGE.format(month=f"{MONTHS[cur.month-1]} {cur.year}", lag_wks=lag_wks,
                        total=f"{tot:,.0f}", spend_m=f"{mval/1e6:.0f}",
                        shelf_rows=shelf_rows, shelf_lede=shelf_lede, journey=journey,
                        strip=strip, whole_note=whole_note,
                        imports=f"{s['imports_kt']:.0f}", spend_yr=f"{s['imports_gbp_m']:.0f}",
                        ss=f"{s['ss']:.1f}", world_rank=world_rank, rex=rex, world=world,
                        market=market, board=board, relay=relay_cells,
                        relay_legend=relay_legend, sells=sells,
                        generated=_dt.date.today().isoformat())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    return html


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Britain's Blueberry Board</title>
<style>
 :root{{--ink:#2a2622;--accent:#5a3fb0;--up:#157a33;--down:#a8281c;--line:#dcd4c4;--mut:#5f564a}}
 *{{box-sizing:border-box}}
 body{{margin:0;color:var(--ink);background:#ece6d8;line-height:1.4;
   font-family:"Helvetica Neue",Arial,sans-serif;font-weight:700;font-stretch:condensed}}
 .wrap{{max-width:900px;margin:0 auto;padding:52px 34px 110px}}
 .masthead{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:8px}}
 .head{{min-width:0}}
 .hero{{width:184px;height:auto;flex:none;filter:drop-shadow(0 6px 14px rgba(42,38,34,.22))}}
 .kick{{text-transform:uppercase;letter-spacing:.2em;font-size:.72rem;color:var(--accent);font-weight:800}}
 h1{{font-size:2.6rem;margin:.12em 0 .1em;letter-spacing:-.02em;color:var(--ink)}}
 .idx{{font-size:1rem;color:#6a6052;border-top:2px solid var(--line);border-bottom:2px solid var(--line);
   padding:18px 0;margin:20px 0 8px;font-weight:700;line-height:1.7}}
 .idx b{{color:var(--accent)}}
 .idx .sub{{display:block;font-size:.72rem;color:var(--mut);font-weight:700;text-transform:uppercase;
   letter-spacing:.08em;margin-bottom:10px}}
 .shrow{{display:flex;align-items:baseline;gap:.6em 1.4em;flex-wrap:wrap;padding:20px 6px;
   border-bottom:1px solid var(--line)}}
 .shrow .nm{{font-size:1.5rem;font-weight:800;min-width:9ch}}
 .packs{{display:flex;flex-wrap:wrap;gap:.7em 1.4em;align-items:baseline}}
 .pk{{font-size:1.5rem;color:var(--ink);white-space:nowrap}}
 .pk .sz{{font-size:.92rem;color:var(--mut);font-weight:800;margin-right:.15em}}
 h2{{text-transform:uppercase;letter-spacing:.12em;font-size:.82rem;color:var(--accent);
   margin:64px 0 5px;font-weight:800}}
 .lede{{margin:0 0 24px;font-size:.86rem;color:var(--mut);font-weight:700;line-height:1.5}}
 .strip{{display:flex;flex-wrap:wrap;align-items:baseline;gap:.6em 1.5em;font-size:1.15rem;
   padding:20px 6px 6px;line-height:1.6}}
 .strip .sl{{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--mut);
   font-weight:800;margin-right:.3em}}
 .aside{{font-size:.92rem;color:var(--mut);font-weight:700;line-height:1.6;margin:20px 0 6px;
   padding:16px 18px;border-left:3px solid var(--line);background:#0000000a;border-radius:0 6px 6px 0}}
 .aside .tag{{display:inline-block;font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;
   color:#fff;background:#bcb3a0;border-radius:3px;padding:1px 6px;margin-right:.4em;vertical-align:.1em}}
 .aside b{{color:var(--ink)}}
 .tk{{display:flex;align-items:baseline;gap:.6em 1.1em;flex-wrap:wrap;padding:20px 6px;
   border-bottom:1px solid var(--line)}}
 .sym{{display:inline-flex;flex-direction:column;align-self:center;min-width:4.2ch}}
 .sym .code{{font-size:2.3rem;font-weight:800;letter-spacing:-.03em;line-height:.95}}
 .sym .cty{{font-size:.62rem;font-weight:700;color:var(--mut);text-transform:uppercase;
   letter-spacing:.05em;white-space:nowrap}}
 .vol{{font-size:1.5rem;color:#4a4339}}
 .shr{{font-size:1.05rem;color:var(--mut);font-weight:800}}
 .at{{color:#8a7f6f;font-size:1.2rem}}
 .px{{font-size:2.1rem;color:var(--ink)}}
 .small-lane{{font-size:.95rem;color:var(--mut);font-style:italic;font-weight:700;align-self:center}}
 .chg{{font-size:1.6rem}} .up{{color:var(--up)}} .down{{color:var(--down)}} .flat{{color:var(--mut)}}
 .chip{{font-size:.78rem;padding:2px 8px;border-radius:20px;font-weight:800;align-self:center;
   background:#fff8}} .chip.up{{color:var(--up)}} .chip.down{{color:var(--down)}} .chip.flat{{color:var(--mut)}}
 .relay{{display:grid;grid-template-columns:repeat(12,1fr);gap:8px}}
 .rc{{border:2px solid var(--line);border-radius:7px;padding:12px 3px;text-align:center;
   background:#fffefb}}
 .rc b{{display:block;font-size:.66rem;color:var(--mut);letter-spacing:.05em;margin-bottom:3px}}
 .rc span{{font-size:.92rem;font-weight:800}}
 .rc.now{{box-shadow:0 0 0 2px var(--accent) inset;background:#fff}}
 .rc i{{display:block;font-size:.5rem;font-style:normal;font-weight:800;color:var(--accent);
   text-transform:uppercase;letter-spacing:.08em;margin-top:3px}}
 .relay-key{{margin:18px 2px 0;font-size:.82rem;color:var(--mut);font-weight:700;line-height:2}}
 .sell{{display:flex;align-items:center;gap:1em;padding:15px 6px;border-bottom:1px solid var(--line)}}
 .sell .sym{{min-width:7ch}} .sell .sym .code{{font-size:1.5rem}} .arrow{{color:#aaa091}}
 .dests{{font-size:1.05rem;color:#5a5347;font-weight:700}}
 .bbar{{display:flex;height:38px;border-radius:7px;overflow:hidden;border:1px solid var(--line);
   margin-top:6px}}
 .bbar .seg{{display:block;height:100%}}
 .seg.border,.dot.border{{background:#6b3fa0}}
 .seg.dist,.dot.dist{{background:#b9a7e0}}
 .seg.retail,.dot.retail{{background:#e8833a}}
 .bends{{display:flex;justify-content:space-between;align-items:baseline;margin-top:8px;
   font-size:1.05rem;font-weight:800;color:var(--ink)}}
 .bends span:nth-child(2){{font-size:.82rem;color:var(--accent)}}
 .bcont{{margin-top:12px;font-size:1.05rem;color:var(--ink);font-weight:700;line-height:1.5}}
 .bcont b{{color:var(--accent)}}
 .bcont .src{{display:block;font-size:.7rem;color:var(--mut);font-weight:700;font-style:italic;
   text-transform:none;letter-spacing:0;margin-top:2px}}
 .blegend{{margin-top:20px}}
 .bl{{display:flex;align-items:baseline;gap:.6em 1em;flex-wrap:wrap;padding:9px 2px}}
 .bl .dot{{width:.85em;height:.85em;border-radius:2px;align-self:center;flex:none}}
 .bl .blk{{font-weight:800;min-width:14ch}}
 .bl .blv{{font-size:1.2rem;color:var(--accent);font-weight:800;min-width:4ch}}
 .bl .blp{{color:var(--mut);font-weight:800;min-width:3ch}}
 .bl .bls{{font-size:.74rem;color:var(--mut);font-weight:700;font-style:italic}}
 .tier{{font-size:.6rem;text-transform:uppercase;letter-spacing:.04em;color:#fff;
   background:#bcb3a0;border-radius:3px;padding:1px 5px;margin-left:.25em;vertical-align:.12em}}
 .note{{font-size:1rem;color:var(--mut);font-weight:700;padding:16px 4px;line-height:1.65;margin:4px 0}}
 .note b{{color:var(--accent)}}
 .world,.world3{{display:grid;grid-template-columns:1fr 1fr;gap:20px 36px;margin-top:6px}}
 .world3{{grid-template-columns:1fr 1fr 1fr}}
 .world h3{{font-size:.74rem;text-transform:uppercase;letter-spacing:.1em;color:var(--accent);
   margin:8px 0 2px;font-weight:800}}
 .wsub{{font-size:.6rem;color:var(--mut);font-weight:700;text-transform:uppercase;
   letter-spacing:.04em;margin-bottom:10px;line-height:1.35}}
 .wr{{display:flex;align-items:baseline;gap:.35em .5em;flex-wrap:wrap;padding:10px 2px;
   border-bottom:1px solid var(--line)}}
 .wr .wc{{flex:1 1 100%;font-size:.92rem;font-weight:800;color:var(--ink)}}
 .wr .wv{{font-size:1.05rem;color:var(--accent);font-weight:800}}
 .wr .wy{{font-size:.72rem;font-weight:800}}
 .wr .wy.up{{color:var(--up)}} .wr .wy.down{{color:var(--down)}} .wr .wy.flat{{color:var(--mut)}}
 .wr .wk{{font-size:.78rem;color:var(--mut);margin-left:auto}}
 @media(max-width:560px){{.world,.world3{{grid-template-columns:1fr}}}}
 .mr{{display:flex;align-items:baseline;gap:.8em 1.2em;flex-wrap:wrap;padding:18px 6px;
   border-bottom:1px solid var(--line)}}
 .mr .mc{{font-size:1.5rem;font-weight:800;color:var(--ink);min-width:9ch}}
 .mr .mv{{font-size:1.8rem;color:var(--accent);font-weight:800;min-width:5ch}}
 .mr .mbar{{flex:1;min-width:90px;height:9px;background:#e2dac9;border-radius:5px;overflow:hidden}}
 .mr .mbar i{{display:block;height:100%;background:var(--accent);opacity:.55}}
 .mr .mbar.exp i{{background:repeating-linear-gradient(45deg,#2a9d8f,#2a9d8f 5px,#3fb0a2 5px,#3fb0a2 10px)}}
 .mr .ms{{font-size:.9rem;color:var(--mut);font-weight:700;min-width:13ch;text-align:right}}
 .foot{{margin-top:72px;border-top:2px solid var(--line);padding-top:24px;font-size:.78rem;
   color:var(--mut);font-weight:700;line-height:1.8}}
 .foot a{{color:var(--accent)}}
 @media(max-width:560px){{h1{{font-size:2rem}}.sym .code{{font-size:1.8rem}}.px{{font-size:1.6rem}}
   .mr .mv{{font-size:1.5rem}}.bl .blk{{min-width:11ch}}
   .relay{{grid-template-columns:repeat(6,1fr)}}.hero{{width:112px}}}}
</style></head><body><div class="wrap">
<div class="masthead">
 <div class="head">
  <div class="kick"><span aria-hidden="true">🫐</span> the UK fresh-blueberry market</div>
  <h1>Britain's Blueberry Board</h1>
 </div>
 <img class="hero" src="hero.png" alt="A British blueberry in a navy suit and Union-Jack tie">
</div>
<div class="idx"><span class="sub">data through {month} · latest settled HMRC month · ~{lag_wks} wks behind today · other sections carry their own date</span>
This month <b>{total} t</b> / <b>£{spend_m}m</b> landed &nbsp;·&nbsp; year <b>{imports}K t</b> / <b>£{spend_yr}m</b> &nbsp;·&nbsp; UK-grown <b>{ss}%</b>{world_rank}</div>

<h2>Who's landing this month</h2>
<p class="lede">{month} · tonnes · share · landed £/kg · ▲▼ vs last month · y/y volume (material lanes only)</p>
{board}

<h2>The price journey</h2>
<p class="lede">where a kilo's shelf price comes from · border &amp; shelf measured, split modelled</p>
{journey}
{strip}
{whole_note}

<h2>On the shelf this week</h2>
<p class="lede">{shelf_lede}</p>
{shelf_rows}

<h2>The relay</h2>
<p class="lede">who leads UK supply each month · typical year (5-yr pattern)</p>
<div class="relay">{relay}</div>
<div class="relay-key">{relay_legend}</div>

<h2>Where each origin sends its fruit</h2>
<p class="lede">2024 · % of their tonnage · includes the UK</p>
{sells}
{rex}

{world}

{market}

<div class="foot">As-of dates vary by source: imports/re-exports through {month} (HMRC OTS, the latest settled
month, ~6–12 wks behind today); shelf this week (Trolley); world trade/production latest complete year
(UN Comtrade + FAOSTAT); UK production + wholesale (DEFRA). Auto-updates weekly ·
<a href="deep.html">full editorial view →</a> · generated {generated}.</div>
</div></body></html>"""


if __name__ == "__main__":
    build()
    print(f"wrote {OUT}")
