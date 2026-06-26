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
from deep.data import ons_price
from core import player_exports, uk_production
from core.fruit import FRUITS, BLUEBERRY

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# Per-fruit render context — set by build(fruit). The vintage-reading helpers and
# the rendering maps below read off the active fruit, so the whole board is just
# re-run per fruit in a loop. CODE/COLR derive from the fruit's supply_origins.
_FRUIT = BLUEBERRY
CODE: dict = {}
COLR: dict = {}


def _ser(prefix: str, suffix: str) -> str:
    """Active fruit's vintage series name, e.g. ('hmrc','imports') -> hmrc_<slug>_imports."""
    return _FRUIT.series(prefix, suffix)


def _set_fruit(fruit) -> None:
    global _FRUIT, CODE, COLR
    _FRUIT = fruit
    CODE = {name: code for name, (_m, code, _c) in fruit.supply_origins.items()}
    COLR = {name: col for name, (_m, _code, col) in fruit.supply_origins.items()}


_set_fruit(BLUEBERRY)
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
PRICE_FLOOR_SHARE = 1.0   # % of the month: suppress @£/kg + ▲▼ below this (a sub-1%
                          # lane is a single premium/air-freight consignment whose unit
                          # value — e.g. Ghana pineapple at £6/kg vs Costa Rica's £0.61
                          # — is real but unrepresentative, so we show "small lane")
YOY_MIN_SHARE = 3.0       # % of the month  } both required for a y/y chip
YOY_MIN_T = 500           # tonnes          } (kills big % on tiny bases)
INSEASON_MIN_SHARE = 2.0  # % of 3-yr supply: in-season strip shows material lanes only
RELAY_MAX_LANES = 8       # "who's landing this month" caps to the top-N material lanes

# --- Price build-up: literature margin/shrink assumptions (sourced; all ESTIMATES) ---
# Used only to DECOMPOSE the measured border→shelf spread, never to invent a price.
RETAIL_GROSS_MARGIN = 0.308   # realized produce-dept gross margin — NGA / Nutrition
#                               Incentive Hub, "Retail Grocery Pricing: A Primer" (2020)
FRESH_FRUIT_SHRINK = 0.126    # fresh-fruit retail shrink by weight — USDA ERS,
#                               Buzby et al. EIB-155 (2016); soft berries run higher
RETAIL_NET_MARGIN = 0.017     # food-retail net profit margin — FMI, Food Retailing
#                               Industry Speaks (2024); berries often a loss-leader
#                               (Richards & Hamilton, AJAE 88(3), 2006)
# Net fruit per 40-ft reefer — the cross-fruit reference for any commodity that
# reuses this board. A 40-ft HC reefer takes ~20 standard (1×1.2 m) pallets in a
# single layer (no double-stacking of fresh produce, airflow gaps) — carrier/
# logistics specs: ICE Transport, FreightAmigo, RFL Cargo, "20-23 pallets". At
# ~1 t of fruit per pallet that is ~20 t net. Light clamshell fruit (berries,
# cherries, grapes) is VOLUME-bound at roughly this; dense fruit (apples, citrus,
# stone fruit) is WEIGHT-bound nearer the reefer's ~26-28 t payload cap. So ~20 t
# is the planning figure; set per-commodity when copied to another fruit.
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


def _last(df, col) -> float:
    """Latest non-null value of `col` in a year-indexed frame (0.0 if absent) — robust
    to a trailing year that carries value/yield but no production yet."""
    if df is None or df.empty or col not in df:
        return 0.0
    s = df[col].dropna()
    return float(s.iloc[-1]) if not s.empty else 0.0


def _board():
    v = vintage.latest(_ser("hmrc", "imports")).copy(); v["d"] = pd.to_datetime(v["ref_period"])
    val = vintage.latest(_ser("hmrc", "import_value")).copy(); val["d"] = pd.to_datetime(val["ref_period"])
    # Pick the month "who's landing now" snapshots. HMRC OTS lands ~6 wks late so
    # a month is only *settled* once ≥70 days old. And for a SEASONAL fruit the
    # latest settled month can be its off-season trough (e.g. cherries in April →
    # ~0 t), which makes the snapshot look broken — so we anchor on the latest
    # settled *active* month: total ≥ 20% of the fruit's own monthly average.
    ms = _months(v)
    today = pd.Timestamp(_dt.date.today())
    settled = [m for m in ms if (today - pd.Timestamp(m)).days >= 70]
    mvol = v.groupby("d")["value"].sum()
    base = settled[-12:] if len(settled) >= 12 else settled
    floor = 0.20 * (mvol[base].mean() if base else 0)
    active = [m for m in settled if mvol.get(m, 0) >= floor]
    use = active if len(active) >= 2 else (settled if len(settled) >= 2 else ms)
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



def _inseason_cif(years=3, frac=0.25, min_t=2000, min_share=INSEASON_MIN_SHARE):
    """Per-origin volume-weighted CIF £/kg over each origin's *in-season* months
    (months where it moves ≥`frac` of its own peak month), last `years` years,
    for the origins that are *material* to UK supply — carrying ≥`min_t` tonnes AND
    ≥`min_share`% of the fruit's total imports in that window. The share gate is
    what scales across a 68 kt fruit (blueberry) and a 1 Mt one (banana): it drops
    niche premium lanes (e.g. air-freighted Ghana pineapple at 0.6% of supply, whose
    £3/kg dwarfs the £0.61 sea-freight bulk) that distort the strip without moving
    the market. Returns [(origin, £/kg)] cheapest→dearest.
    """
    v = vintage.latest(_ser("hmrc", "imports")).copy(); v["d"] = pd.to_datetime(v["ref_period"])
    val = vintage.latest(_ser("hmrc", "import_value")).copy(); val["d"] = pd.to_datetime(val["ref_period"])
    cut = v["d"].max() - pd.DateOffset(years=years)
    v, val = v[v["d"] >= cut], val[val["d"] >= cut]
    total = v["value"].sum()
    out = []
    for o in _FRUIT.inseason:
        vo = v[v["key"] == o]
        by_m = vo.groupby("d")["value"].sum()
        if by_m.empty or by_m.max() <= 0:
            continue
        months = by_m[by_m >= frac * by_m.max()].index
        kg = vo[vo["d"].isin(months)]["value"].sum()
        gbp = val[(val["key"] == o) & (val["d"].isin(months))]["value"].sum()
        share = vo["value"].sum() / total * 100 if total else 0
        if kg > min_t and share >= min_share:         # material lane → trustworthy price
            out.append((o, gbp / (kg * 1000)))
    return sorted(out, key=lambda x: x[1])


def _retail(month):
    """UK shelf £/kg for the given month — ONS monthly retail proxy (year-round
    fallback when there's no weekly Trolley feed). Reads the fruit's spliced series
    (direct item £/kg, then its segment index); per-kg items only. NaN if the fruit
    has no ONS series (the 'each'-priced fruit have none — no honest £/kg)."""
    r = vintage.latest(_ser("ons", "retail_price")).copy()
    if r.empty:
        return float("nan")
    r["d"] = pd.to_datetime(r["ref_period"])
    r = r.sort_values("d")                            # direct + spliced, one continuous series
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
        r = vintage.latest(_ser("retail", "price")).copy()
    except Exception:
        return None, float("nan"), [], 0, 0
    if r.empty:
        return None, float("nan"), [], 0, 0
    r["d"] = pd.to_datetime(r["ref_period"])
    r = r[r["d"] == r["d"].max()]
    parts = r["key"].str.split("|", expand=True)
    r["retailer"], r["tier"], r["pack"] = parts[0], parts[1], parts[2]
    per, big, big_g = [], [], []
    for ret, g in r.groupby("retailer"):              # all tiers: standard + finest/organic
        packs = [{"pack": str(t.pack), "kg": float(t.value), "tier": str(t.tier)}
                 for t in g.itertuples()]
        # standard first (by size), then variants (by size)
        packs.sort(key=lambda p: (p["tier"] != "standard", _grams(p["pack"])))
        std = [p for p in packs if p["tier"] == "standard"]
        med_src = std or packs
        if std:
            big.append(std[-1]["kg"])                 # largest STANDARD pack's £/kg
            big_g.append(_grams(std[-1]["pack"]))     # and its size, for the headline label
        per.append({"retailer": ret,
                    "med": float(pd.Series([p["kg"] for p in med_src]).median()),
                    "packs": packs})
    per.sort(key=lambda x: x["med"])
    headline = float(pd.Series(big).median()) if big else float("nan")
    pack_g = int(pd.Series(big_g).median()) if big_g else 0   # typical headline pack size
    return r["d"].max(), headline, per, int(len(r)), pack_g


def _relay(v=None):
    v = v or vintage.latest(_ser("hmrc", "imports")).copy()
    v["d"] = pd.to_datetime(v["ref_period"]); v["m"] = v["d"].dt.month
    recent = v[v["d"] >= v["d"].max() - pd.DateOffset(months=60)]
    lead = (recent.groupby(["m", "key"])["value"].sum().reset_index()
            .sort_values("value").groupby("m").tail(1).set_index("m")["key"])
    return [lead.get(m, "") for m in range(1, 13)]


def _summary():
    v = vintage.latest(_ser("hmrc", "imports")).copy(); v["d"] = pd.to_datetime(v["ref_period"])
    val = vintage.latest(_ser("hmrc", "import_value")).copy(); val["d"] = pd.to_datetime(val["ref_period"])
    l12v = v[v["d"] >= v["d"].max() - pd.DateOffset(months=11)]["value"].sum()
    l12val = val[val["d"] >= val["d"].max() - pd.DateOffset(months=11)]["value"].sum()
    avg = l12val / (l12v * 1000)
    prod = uk_production.load(_FRUIT.slug) if _FRUIT.defra_production else pd.DataFrame()
    pk = _last(prod, "production_kt")            # latest reported UK-grown kt
    ss = pk / (l12v / 1000 + pk) * 100 if l12v else 0
    pv = _last(prod, "value_gbp_m")
    return {"imports_kt": l12v / 1000, "avg": avg, "ss": ss,
            "imports_gbp_m": l12val / 1e6, "uk_value_gbp_m": pv}


def _wholesale():
    """UK wholesale-market £/kg (DEFRA, weekly Jun–Nov) — the price-journey middle.
    Returns (date, £/kg) of the latest reading, or (None, nan) if unheld."""
    try:
        w = vintage.latest(_ser("defra", "price")).copy()
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
        r = vintage.latest(_ser("hmrc", "reexports")).copy()
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
    df = cg.load(_FRUIT.cache("global_trade"))
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
        growers = pr.top_growers(6, pr.load(_FRUIT.cache("global_production")))
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
    tr = cg.load(_FRUIT.cache("global_trade"))
    if tr.empty:
        return None, []
    yr = int(tr["year"].max())
    cur = tr[tr["year"] == yr]
    imp = cur[cur["role"] == "importer"].set_index("country")["net_kg"].div(1e6).to_dict()
    exp = cur[cur["role"] == "exporter"].set_index("country")["net_kg"].div(1e6).to_dict()
    prod = pr.production_by_country(pr.load(_FRUIT.cache("global_production")),
                                    overrides=_FRUIT.production_overrides)
    try:                                              # UK absent from FAOSTAT → DEFRA
        ukp = uk_production.load(_FRUIT.slug) if _FRUIT.defra_production else pd.DataFrame()
        ukt = _last(ukp, "production_kt")
        if ukt and "United Kingdom" not in prod:
            prod["United Kingdom"] = (ukt * 1000, yr, "DEFRA")
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
    col = COLR.get(r["origin"], "#5a3fb0")
    tt = f"{r['t']/1000:.1f}K t" if r["t"] >= 1000 else f"{r['t']:.0f} t"
    shr = f'{r["share"]:.0f}%' if r["share"] >= 1 else "<1%"
    sub = f'{r["origin"]} · {tt} · {shr} of the month'
    # right side: @£/kg + ▲▼ only when the lane carries enough volume to trust it
    if r["share"] >= PRICE_FLOOR_SHARE and r["cif"] == r["cif"]:
        cls, arr = _delta_chip(r["dprice"], "")
        right = (f'<span class="px">£{r["cif"]:.2f}</span>'
                 f'<span class="chg {cls}">{arr} £{abs(r["dprice"]):.2f}</span>')
    else:
        right = '<span class="small-lane">small lane</span>'
    # y/y volume chip: only on a material base; cap tiny-base blow-ups
    yo = ""
    if r["yoy"] == r["yoy"] and r["share"] >= YOY_MIN_SHARE and r["t"] >= YOY_MIN_T:
        y = r["yoy"]
        cls, arr = _delta_chip(y, "")
        lbl = ("±0%" if cls == "flat" else ">+100%" if y >= 100
               else "<-100%" if y <= -100 else f'{"+" if y >= 0 else ""}{y:.0f}%')
        yo = f'<span class="chip {cls}">{arr} {lbl} y/y</span>'
    return (f'<div class="tk">'
            f'<div class="tk-l"><span class="code" style="color:{col}">{r["code"]}</span>'
            f'<span class="sub">{sub}</span></div>'
            f'<div class="tk-r">{right}{yo}</div></div>')


def _money(usd):
    """$ -> compact '$1.9bn' / '$801m'."""
    return f"${usd/1e9:.1f}bn" if usd >= 1e9 else f"${usd/1e6:.0f}m"


def build(fruit=BLUEBERRY) -> str:
    _set_fruit(fruit)
    cur, prev, rows, tot, mavg, mval = _board()
    ct = _FRUIT.container_t                   # fruit per 40-ft reefer (soft 20 / dense 24)
    relay = _relay()
    s = _summary()
    landed = s["avg"]                        # 12-mo volume-weighted blended CIF £/kg
    shelf_wk, shelf, per, n_packs, shelf_pack_g = _shelf()
    shelf_lbl = f"wk {pd.Timestamp(shelf_wk).strftime('%-d %b')}" if shelf_wk is not None else "this wk"
    if shelf != shelf:                       # no Trolley data → ONS monthly proxy
        shelf, shelf_lbl = _retail(cur), "ONS proxy"
    ons_shelf = (shelf_lbl == "ONS proxy") and (shelf == shelf)  # ONS index filled it (finite)
    est_g = ons_price.weight_g(_FRUIT.slug) if ons_shelf else None  # weight-converted estimate?
    if est_g:
        shelf_basis = (f"the <b>ONS monthly retail index</b> ÷ a standard {est_g}&#8201;g fruit "
                       f"(USDA) — an estimate")
    elif ons_shelf:
        shelf_basis = "the <b>ONS monthly retail index</b>"
    else:
        shelf_basis = f"a standard {shelf_pack_g}&#8201;g punnet, {shelf_lbl}"
    shelf_pfx = "≈" if est_g else ""          # mark a weight-estimated shelf £/kg
    when_w, whole = _wholesale()
    rex_kt, rex_top = _reexports()
    wyr, uk_rank, wgro, wexp, wimp = _world()
    cur_m = cur.month
    lag_wks = int((pd.Timestamp(_dt.date.today()) - cur).days / 7)
    # Cap "who's landing this month" to the top material lanes — the long tail of
    # sub-1% origins is all "small lane" filler and just pads the list. Blueberry's
    # 5 lanes are unaffected; banana's ~15 trims to the 8 that carry the month.
    board = "\n".join(_ticker_html(r) for r in rows[:RELAY_MAX_LANES])
    # The price journey — a cost build-up of the measured shelf £/kg: the all-origin
    # LANDED import CIF (12-mo volume-weighted) and the supermarket SHELF (pack-
    # normalised) are MEASURED; the split between them (UK import/distribution vs
    # retailer gross margin) is MODELLED off the NGA produce-margin benchmark.
    # DEFRA wholesale stays an aside (British-season home-grown spot, not a step).
    markup = (f'+{(shelf/landed - 1)*100:.0f}%'
              if (landed == landed and landed > 0 and shelf == shelf) else '')
    # DEFRA British-season wholesale — a caveat aside, not a journey step.
    whole_note = ""
    if whole == whole and when_w is not None:
        whole_note = (f'<div class="aside"><span class="tag">not a journey step</span> '
                      f'UK-grown, British-season <b>wholesale</b> (DEFRA · New Covent Garden) is '
                      f'<b>£{whole:.2f}/kg</b> ({pd.Timestamp(when_w).strftime("%b %Y")}) — premium '
                      f'loose fruit sold spot, a different product/season to imported retail, so it '
                      f'sits above both prices.</div>')
    # Card 1 — the cost build-up (border → shelf). Landed = 12-mo all-origin
    # volume-weighted average; the heavy economics fold into a drop-down.
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
        fl = _FRUIT.name.lower()
        ll = (f' At this blend the spread barely covers a normal retail margin — '
              f'consistent with {fl} sold near break-even.' if loss_leader else '')
        econ_full = (f'That ~{RETAIL_GROSS_MARGIN*100:.0f}% retail slice is gross, not profit: fresh fruit '
                     f'loses <b>{FRESH_FRUIT_SHRINK*100:.0f}%+</b> by weight to shrink (USDA ERS, 2016) — soft '
                     f'fruit more — so the initial markup is set ~40–50% to net it down; food-retail <b>net</b> '
                     f'margin is only ~<b>{RETAIL_NET_MARGIN*100:.1f}%</b> (FMI, 2024), and fresh produce is often '
                     f'run as a deliberate <b>loss-leader</b> in peak season (Richards &amp; Hamilton, 2006).{ll} '
                     + ('Border is measured; shelf is an estimate (ONS ÷ a standard fruit weight); the split is modelled.'
                        if est_g else 'Border &amp; shelf are measured; the split is modelled.'))
        econ = (f'<details class="exp"><summary>The retailer\'s ~{RETAIL_GROSS_MARGIN*100:.0f}% slice is '
                f'<b>gross margin, not profit</b><span class="more">why</span></summary>'
                f'<p class="xp">{econ_full}</p></details>')
        cap = (f'<p class="cap"><b>Landed</b> is the 12-month average across all origins (volume-weighted); '
               f'this month alone runs £{mavg:.2f}. <b>Shelf</b> is {shelf_basis}.</p>')
        journey = (f'<div class="bbar">{bar}</div>'
                   f'<div class="bends"><span>£{landed:.2f} landed</span>'
                   f'<span>{markup}</span><span>{shelf_pfx}£{shelf:.2f} shelf</span></div>'
                   f'{cap}'
                   f'<div class="bcont">A <b>40-ft reefer (~{ct} t)</b> lands at '
                   f'~<b>£{landed*ct:.0f}k</b> and rings up at '
                   f'{"" if shelf_pfx else "~"}<b>{shelf_pfx}£{shelf*ct:.0f}k</b> on shelf.</div>'
                   f'<div class="blegend">{legend}</div>{econ}{whole_note}')
    elif landed == landed:                            # have landed, no shelf feed yet
        journey = (f'<div class="bends"><span>£{landed:.2f}/kg landed</span></div>'
                   f'<div class="bcont">A <b>40-ft reefer (~{ct} t)</b> lands at '
                   f'~<b>£{landed*ct:.0f}k</b>.</div>'
                   f'<p class="note">No supermarket shelf-price feed for '
                   f'{_FRUIT.name.lower()} yet, so the border→shelf build-up isn\'t shown. '
                   f'Landed is the 12-month all-origin average (volume-weighted).</p>')
    else:
        journey = '<p class="note">Insufficient price data.</p>'
    # Card 2 — the per-origin in-season prices that compose the blend, + per-container.
    insn = _inseason_cif()
    inseason = ""
    if insn:
        chips = "".join(
            f'<span class="ic" style="color:{COLR.get(o, "#5a3fb0")}"><b>{CODE.get(o, o[:3].upper())}</b> '
            f'£{c:.2f}<span class="ctr">£{c*ct:.0f}k</span></span>'
            for o, c in insn)
        bound = ('this fruit is a light clamshell/punnet pack, so it fills the ~20 pallets by '
                 '<b>volume</b> before it nears the weight cap' if ct <= 20 else
                 'this fruit cartons densely, so it hits the reefer\'s <b>weight</b> cap '
                 '(~26&#8201;t payload) before it runs out of floor space')
        basis_full = (f'Per-container figures take <b>~{ct}&#8201;t of fruit per 40-ft reefer</b> '
                      f'— ~20 standard (1×1.2&#8201;m) pallets in a single layer (no double-stacking; airflow gaps). '
                      f'Soft berries and clamshell fruit settle near <b>~20&#8201;t</b> (volume-bound); dense cartoned '
                      f'fruit (apples, citrus, stone fruit) loads <b>~24&#8201;t</b> (weight-bound) — {bound}. '
                      f'<span class="src">40-ft HC reefer pallet capacity: ICE Transport · FreightAmigo · RFL Cargo.</span>')
        basis = (f'<details class="exp"><summary>Per-container = <b>~{ct}&#8201;t</b> of fruit per '
                 f'40-ft reefer<span class="more">how</span></summary><p class="xp">{basis_full}</p></details>')
        cheap, dear = insn[0][0], insn[-1][0]
        spread = (f'{cheap} sets the blend almost single-handed' if len(insn) == 1
                  else f'the cheapest lane (<b>{cheap}</b>) pulls the blend down; '
                       f'the dearest (<b>{dear}</b>) lifts it')
        intro = (f'<p class="cap">The per-origin prices that average (volume-weighted) to the '
                 f'<b>£{landed:.2f}</b> landed figure above — {spread}.</p>')
        inseason = (f'{intro}<div class="strip"><span class="sl">£/kg · per {ct}-t reefer</span>'
                    f'{chips}</div>{basis}')
    # UK re-exports (HMRC export flows)
    rex = ""
    if rex_kt == rex_kt and rex_kt > 0:
        dests = ", ".join(f"{_dcode(k)} {v:.1f}kt" for k, v in rex_top)
        rex = (f'<div class="note">↩ The UK also <b>re-exports ~{rex_kt:.1f} kt/yr</b> '
               f'of fresh {_FRUIT.name.lower()} — mostly {dests}.</div>')
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
                f'<div class="wr"><span class="wc">{c}{"†" if c in _FRUIT.production_overrides else ""}</span>'
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
        gap = f'<p class="note">{_FRUIT.gap_note}</p>' if (_FRUIT.production_overrides and _FRUIT.gap_note) else ""
        world = (f'<section class="sec"><div class="shead">'
                 f'<h2>The world\'s {_FRUIT.name.lower()} map</h2>'
                 f'<p class="lede">{rankline}grow → export → import · {wyr} · '
                 f'FAOSTAT production, UN Comtrade trade</p></div>'
                 f'<div class="card"><div class="world3">{cols}</div>{gap}</div></section>')
    # Domestic market — apparent consumption (production + imports − exports)
    cyr, crows = _consumption()
    market = ""
    if crows:
        flagged = any(r[3] and r[3] != "DEFRA" for r in crows)
        mr = ""
        for c, cons, ss, src in crows:
            star = "†" if (src and src != "DEFRA") else ""
            if ss > 105:                               # produces more than it eats
                label = f'net exporter · grows {ss/100:.1f}× its home use'
                bar = '<span class="mbar exp"><i style="width:100%"></i></span>'
            else:
                label = f'{ss:.0f}% home-grown'
                bar = f'<span class="mbar"><i style="width:{min(ss,100):.0f}%"></i></span>'
            mr += (f'<div class="mr"><span class="mc">{c}{star}</span>'
                   f'<span class="mv">{cons:,.0f} kt</span>{bar}'
                   f'<span class="ms">{label}</span></div>')
        ov_note = ""
        if flagged:
            ov = "; ".join(f'<b>{c}</b> ~{t/1000:.0f} kt, {src}'
                           for c, (t, _yr, src) in _FRUIT.production_overrides.items())
            ov_note = (f'† {ov} — sourced industry estimate(s), not in FAOSTAT; '
                       f'all other production is FAOSTAT (UK: DEFRA). ')
        # Honesty: this is apparent AVAILABILITY, not literal eating — it isn't netted
        # for spoilage/processing, which is large for perishable fruit (e.g. India keeps
        # ~all its mango, but a big share is lost or pulped, not eaten fresh).
        foot = (f'<p class="note">{ov_note}Apparent consumption is what each market keeps '
                f'<b>available</b> (production + net imports) — not what is literally eaten: it is '
                f'not netted for the share lost to spoilage or diverted to juice/processing, which '
                f'is large for perishable fruit.</p>')
        market = (f'<section class="sec"><div class="shead">'
                  f'<h2>Domestic market — who keeps it home</h2>'
                  f'<p class="lede">apparent consumption = production + imports − exports · {cyr}'
                  f' · de-hubs the re-exporters</p></div>'
                  f'<div class="card">{mr}{foot}</div></section>')
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
    if per:
        shelf_lede = (f"{len(per)} of 11 retailers · {n_packs} packs · w/c {shelf_when} · "
                      f"£/kg = pack price ÷ weight, so small punnets read dearer")
    elif est_g:                                       # ONS prices it "each" → £/kg via a standard weight
        fl = _FRUIT.name.lower()
        shelf_rows = (f'<p class="note">{_FRUIT.name} is sold <b>by the each</b>, so ONS quotes it per fruit, '
                      f'not per kilo. The journey above converts the <b>ONS monthly retail index</b> to '
                      f'<b>≈£{shelf:.2f}/kg</b> using a standard <b>{est_g} g</b> {fl} (USDA) — a sourced '
                      f'estimate, not a measured shelf £/kg, so treat it as indicative.</p>')
        shelf_lede = f"sold by the each · £/kg estimated via a standard {est_g} g fruit"
    elif ons_shelf:                                   # no weekly Trolley feed, but ONS prices it per kg
        fl = _FRUIT.name.lower()
        shelf_rows = (f'<p class="note">No weekly per-retailer feed for {fl} — it sells mostly '
                      f'<b>loose or by the each</b>, so there\'s no per-pack price to scrape weekly. '
                      f'The journey above instead uses the <b>ONS monthly retail index</b> '
                      f'(£{shelf:.2f}/kg) — the pre-2025 item £/kg spliced forward by its CPI segment.</p>')
        shelf_lede = "no weekly feed — journey uses the ONS monthly retail index"
    else:                                             # not tracked by Trolley or ONS
        fl = _FRUIT.name.lower()
        shelf_rows = (f'<p class="note">No retail price feed for {fl}: neither the weekly Trolley basket nor '
                      f'the ONS Shopping Prices tool tracks it, so there\'s no honest £/kg shelf figure. The '
                      f'<b>landed</b> figure above is the reliable border benchmark.</p>')
        shelf_lede = "not tracked by Trolley or ONS — no shelf feed"
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
    pe = player_exports.load(_FRUIT.cache("player_destinations"))
    sells = ""
    if not pe.empty:
        for p in _FRUIT.inseason:
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
    # Headline KPI cards — the summary stats, each its own card so they read distinct
    kpi = [("This month", f"{tot:,.0f} t", f"£{mval/1e6:.0f}m landed"),
           ("Per year", f"{s['imports_kt']:.0f}K t", f"£{s['imports_gbp_m']:.0f}m imported"),
           ("UK-grown", f"{s['ss']:.1f}%" if _FRUIT.defra_production else "n/a",
            "of all supply" if _FRUIT.defra_production else "no DEFRA data")]
    if uk_rank:
        kpi.append(("World rank", f"#{uk_rank}", f"{_FRUIT.name.lower()} importer"))
    kpis = "".join(f'<div class="kpi"><span class="kl">{l}</span>'
                   f'<span class="kv">{v}</span><span class="ku">{u}</span></div>'
                   for l, v, u in kpi)
    emoji_html = f'<span aria-hidden="true">{_FRUIT.emoji}</span> ' if _FRUIT.emoji else ''
    html = _PAGE.format(month=f"{MONTHS[cur.month-1]} {cur.year}", lag_wks=lag_wks,
                        commodity=_FRUIT.name, commodity_lc=_FRUIT.name.lower(), emoji_html=emoji_html,
                        kpis=kpis, shelf_rows=shelf_rows, shelf_lede=shelf_lede, journey=journey,
                        inseason=inseason, rex=rex, world=world,
                        market=market, board=board, relay=relay_cells,
                        relay_legend=relay_legend, sells=sells, container_t=ct,
                        generated=_dt.date.today().isoformat())
    fruit.out.parent.mkdir(parents=True, exist_ok=True)
    fruit.out.write_text(html, encoding="utf-8")
    return html


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Britain's {commodity} Board</title>
<style>
 :root{{--ink:#241f1a;--accent:#5a3fb0;--up:#1a7f37;--down:#c0392b;--mut:#7a7163;
   --card:#fdfbf7;--hair:#efe8da;--bg:#e8e1d3;
   --sans:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
   --serif:ui-serif,"New York",Georgia,"Times New Roman",serif}}
 *{{box-sizing:border-box}}
 body{{margin:0;color:var(--ink);background:var(--bg);font-family:var(--sans);line-height:1.45;
   -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}}
 .wrap{{max-width:760px;margin:0 auto;padding:46px 20px 100px}}
 .back{{display:inline-block;margin-bottom:18px;font-size:.78rem;font-weight:600;
   letter-spacing:.02em;color:var(--mut);text-decoration:none}}
 .back:hover{{color:var(--accent)}}
 .masthead{{margin-bottom:2px}}
 .kick{{text-transform:uppercase;letter-spacing:.16em;font-size:.7rem;color:var(--accent);font-weight:700}}
 h1{{font-size:2.5rem;line-height:1.04;margin:.16em 0 0;letter-spacing:-.025em;font-weight:800;color:var(--ink)}}
 .stamp{{margin:26px 0 13px;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
   color:var(--mut);font-weight:600}}
 .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:13px}}
 .kpi{{background:var(--card);border-radius:18px;padding:17px 19px;
   box-shadow:0 1px 2px rgba(36,31,26,.05),0 14px 28px -16px rgba(36,31,26,.22)}}
 .kl{{font-size:.66rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);font-weight:700}}
 .kv{{display:block;font-size:1.95rem;font-weight:800;letter-spacing:-.025em;margin:4px 0 1px;color:var(--ink)}}
 .ku{{font-size:.8rem;color:var(--mut);font-weight:600}}
 .sec{{margin-top:42px}}
 .shead{{margin:0 4px 13px}}
 h2{{font-size:1.34rem;font-weight:800;letter-spacing:-.02em;color:var(--ink);margin:0}}
 .lede{{margin:4px 0 0;font-size:.9rem;color:var(--mut);font-weight:500;line-height:1.45}}
 .card{{background:var(--card);border-radius:22px;padding:4px 22px;
   box-shadow:0 1px 2px rgba(36,31,26,.05),0 20px 38px -22px rgba(36,31,26,.26)}}
 .tk{{display:flex;justify-content:space-between;align-items:center;gap:1em;
   padding:16px 2px;border-bottom:1px solid var(--hair)}}
 .tk:last-child{{border-bottom:none}}
 .tk-l{{min-width:0}}
 .tk-l .code{{font-size:1.7rem;font-weight:800;letter-spacing:-.02em}}
 .tk-l .sub{{display:block;font-size:.82rem;color:var(--mut);font-weight:600;margin-top:1px}}
 .tk-r{{display:flex;align-items:baseline;gap:.55em;flex:none}}
 .tk-r .px{{font-size:1.6rem;font-weight:800;color:var(--ink)}}
 .chg{{font-size:1rem;font-weight:700}} .up{{color:var(--up)}} .down{{color:var(--down)}} .flat{{color:var(--mut)}}
 .small-lane{{font-size:.92rem;color:var(--mut);font-style:italic}}
 .chip{{font-size:.72rem;padding:3px 9px;border-radius:20px;font-weight:700;
   background:#00000008}} .chip.up{{color:var(--up)}} .chip.down{{color:var(--down)}} .chip.flat{{color:var(--mut)}}
 .shrow{{display:flex;align-items:baseline;gap:.6em 1.2em;flex-wrap:wrap;padding:16px 2px;
   border-bottom:1px solid var(--hair)}}
 .shrow:last-child{{border-bottom:none}}
 .shrow .nm{{font-size:1.25rem;font-weight:800;min-width:8ch}}
 .packs{{display:flex;flex-wrap:wrap;gap:.5em 1.2em;align-items:baseline}}
 .pk{{font-size:1.2rem;color:var(--ink);font-weight:700;white-space:nowrap}}
 .pk .sz{{font-size:.8rem;color:var(--mut);font-weight:700;margin-right:.15em}}
 .tier{{font-size:.58rem;text-transform:uppercase;letter-spacing:.04em;color:#fff;background:#bcb3a0;
   border-radius:5px;padding:1px 5px;margin-left:.25em;vertical-align:.1em;font-weight:700}}
 .bbar{{display:flex;height:40px;border-radius:11px;overflow:hidden;margin-top:10px}}
 .bbar .seg{{height:100%}}
 .seg.border,.dot.border{{background:#5a3fb0}}
 .seg.dist,.dot.dist{{background:#b9a7e0}}
 .seg.retail,.dot.retail{{background:#e8833a}}
 .bends{{display:flex;justify-content:space-between;align-items:baseline;margin-top:11px;
   font-size:1.3rem;font-weight:800;color:var(--ink)}}
 .bends span:nth-child(2){{font-size:.9rem;color:var(--accent);font-weight:700}}
 .bcont{{margin-top:15px;font-family:var(--serif);font-size:1.02rem;color:#3a342b;line-height:1.55}}
 .bcont b{{color:var(--accent);font-weight:700}}
 .bcont .src{{display:block;font-size:.8rem;color:var(--mut);font-style:italic;margin-top:3px}}
 .blegend{{margin:18px 0 2px}}
 .bl{{display:flex;align-items:baseline;gap:.55em 1em;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid var(--hair)}}
 .bl:last-child{{border-bottom:none}}
 .bl .dot{{width:.8em;height:.8em;border-radius:3px;align-self:center;flex:none}}
 .bl .blk{{font-weight:700;min-width:13ch}}
 .bl .blv{{font-size:1.2rem;color:var(--accent);font-weight:800;min-width:4ch}}
 .bl .blp{{color:var(--mut);font-weight:700;min-width:3ch}}
 .bl .bls{{font-family:var(--serif);font-size:.8rem;color:var(--mut);font-style:italic}}
 .strip{{display:flex;flex-wrap:wrap;align-items:baseline;gap:.55em 1.3em;font-size:1.05rem;
   font-weight:700;margin-top:18px;padding-top:16px;border-top:1px solid var(--hair);line-height:1.6}}
 .strip .sl{{font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);
   font-weight:700;margin-right:.3em}}
 .strip .ic{{white-space:nowrap}}
 .strip .ctr{{font-size:.78rem;color:var(--mut);font-weight:600;margin-left:.3em}}
 .aside{{font-family:var(--serif);font-size:.96rem;color:#3a342b;line-height:1.6;margin-top:16px;
   padding:13px 16px;border-radius:12px;background:#00000007}}
 .aside .tag{{display:inline-block;font-family:var(--sans);font-size:.58rem;text-transform:uppercase;
   letter-spacing:.08em;color:#fff;background:#bcb3a0;border-radius:5px;padding:2px 7px;
   margin-right:.5em;vertical-align:.1em;font-weight:700}}
 .aside b{{color:var(--ink);font-weight:700}}
 .note{{font-family:var(--serif);font-size:1rem;color:#3a342b;line-height:1.65;margin:14px 0 2px}}
 .note b{{color:var(--accent);font-weight:700}}
 .note .src,.xp .src{{font-size:.8rem;color:var(--mut);font-style:italic}}
 .cap{{font-family:var(--serif);font-size:.92rem;color:#3a342b;line-height:1.55;margin:12px 0 2px}}
 .cap b{{color:var(--ink);font-weight:700}}
 .exp{{margin-top:16px;padding-top:14px;border-top:1px solid var(--hair)}}
 .exp summary{{cursor:pointer;list-style:none;display:flex;align-items:center;gap:.6em;
   font-size:.96rem;font-weight:600;color:var(--ink)}}
 .exp summary::-webkit-details-marker{{display:none}}
 .exp summary b{{color:var(--accent);font-weight:700}}
 .exp summary .more{{margin-left:auto;flex:none;font-size:.66rem;text-transform:uppercase;
   letter-spacing:.06em;color:var(--mut);font-weight:700;border:1px solid var(--hair);
   border-radius:20px;padding:4px 11px;background:#fff}}
 .exp summary .more::after{{content:" ⌄";font-weight:800}}
 .exp[open] summary .more::after{{content:" ⌃"}}
 .xp{{font-family:var(--serif);font-size:.96rem;color:#3a342b;line-height:1.65;margin:11px 0 2px}}
 .xp b{{color:var(--accent);font-weight:700}}
 .relay{{display:grid;grid-template-columns:repeat(12,1fr);grid-auto-rows:1fr;gap:7px;padding:8px 0}}
 .rc{{border:1px solid var(--hair);border-radius:11px;padding:11px 2px;text-align:center;background:#fff;
   display:flex;flex-direction:column;justify-content:center}}
 .rc b{{display:block;font-size:.62rem;color:var(--mut);font-weight:600;margin-bottom:3px}}
 .rc span{{font-size:.9rem;font-weight:800}}
 .rc.now{{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}}
 .rc i{{display:block;font-size:.46rem;font-style:normal;font-weight:800;color:var(--accent);
   text-transform:uppercase;letter-spacing:.05em;margin-top:3px}}
 .relay-key{{margin:12px 2px 6px;font-size:.82rem;color:var(--mut);font-weight:500;line-height:1.9}}
 .relay-key b{{font-weight:800}}
 .sell{{display:flex;align-items:center;gap:.9em;padding:14px 2px;border-bottom:1px solid var(--hair)}}
 .sell:last-child{{border-bottom:none}}
 .sell .sym{{display:inline-flex;flex-direction:column;min-width:6ch}}
 .sell .sym .code{{font-size:1.25rem;font-weight:800;letter-spacing:-.02em}}
 .sell .sym .cty{{font-size:.58rem;color:var(--mut);text-transform:uppercase;letter-spacing:.04em;font-weight:600}}
 .arrow{{color:#bcb3a0}}
 .dests{{font-size:1rem;color:var(--ink);font-weight:600}}
 .world3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px 26px;padding:6px 0}}
 .wcol h3{{font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);
   font-weight:800;margin:6px 0 1px}}
 .wsub{{font-size:.6rem;color:var(--mut);font-weight:600;text-transform:uppercase;
   letter-spacing:.03em;margin-bottom:9px;line-height:1.3}}
 .wr{{display:flex;align-items:baseline;gap:.3em .5em;flex-wrap:wrap;padding:9px 0;border-bottom:1px solid var(--hair)}}
 .wr:last-child{{border-bottom:none}}
 .wr .wc{{flex:1 1 100%;font-size:.92rem;font-weight:700;color:var(--ink)}}
 .wr .wv{{font-size:1.2rem;color:var(--accent);font-weight:800}}
 .wr .wy{{font-size:.7rem;font-weight:700}}
 .wr .wy.up{{color:var(--up)}} .wr .wy.down{{color:var(--down)}} .wr .wy.flat{{color:var(--mut)}}
 .wr .wk{{font-size:.76rem;color:var(--mut);margin-left:auto;font-weight:600}}
 .mr{{display:flex;align-items:center;gap:.8em 1.1em;flex-wrap:wrap;padding:16px 2px;border-bottom:1px solid var(--hair)}}
 .mr:last-child{{border-bottom:none}}
 .mr .mc{{font-size:1.2rem;font-weight:800;color:var(--ink);min-width:8ch}}
 .mr .mv{{font-size:1.5rem;color:var(--accent);font-weight:800;min-width:5ch}}
 .mr .mbar{{flex:1;min-width:80px;height:8px;background:#e8e1d3;border-radius:5px;overflow:hidden}}
 .mr .mbar i{{display:block;height:100%;background:var(--accent);opacity:.5;border-radius:5px}}
 .mr .mbar.exp i{{background:repeating-linear-gradient(45deg,#2a9d8f,#2a9d8f 5px,#3fb0a2 5px,#3fb0a2 10px)}}
 .mr .ms{{font-size:.82rem;color:var(--mut);font-weight:600;min-width:13ch;text-align:right}}
 .foot{{margin-top:50px;font-family:var(--serif);font-size:.82rem;color:var(--mut);line-height:1.75}}
 .foot a{{color:var(--accent)}}
 @media(max-width:620px){{
   .world3{{grid-template-columns:1fr;gap:2px 0}} .wcol{{margin-top:10px}}
   h1{{font-size:2.1rem}} .kv{{font-size:1.7rem}}
   .relay{{grid-template-columns:repeat(6,1fr)}}
   .tk-l .code{{font-size:1.5rem}} .tk-r .px{{font-size:1.42rem}}
   .bl .blk{{min-width:11ch}}
   .strip{{flex-direction:column;align-items:center;text-align:center;gap:.5em}}
   .strip .sl{{margin:0 0 4px}}
 }}
</style></head><body><div class="wrap">
<a class="back" href="index.html">← All fruit boards</a>
<header class="masthead">
 <div class="kick">{emoji_html}the UK fresh-{commodity_lc} market</div>
 <h1>Britain's {commodity} Board</h1>
</header>
<p class="stamp">data through {month} · latest settled HMRC month · ~{lag_wks} wks behind today</p>
<div class="kpis">{kpis}</div>

<section class="sec"><div class="shead"><h2>Who's landing this month</h2>
<p class="lede">{month} · by share · landed £/kg, ▲▼ vs last month · y/y volume (material lanes only)</p></div>
<div class="card">{board}</div></section>

<section class="sec"><div class="shead"><h2>The price journey</h2>
<p class="lede">border to shelf · what a kilo costs at each stage · measured ends, modelled split</p></div>
<div class="card">{journey}</div></section>

<section class="sec"><div class="shead"><h2>In season, landed by origin</h2>
<p class="lede">the cheaper counter-season prices behind the blend · with value per {container_t}-t reefer</p></div>
<div class="card">{inseason}</div></section>

<section class="sec"><div class="shead"><h2>On the shelf this week</h2>
<p class="lede">{shelf_lede}</p></div>
<div class="card">{shelf_rows}</div></section>

<section class="sec"><div class="shead"><h2>The relay</h2>
<p class="lede">who leads UK supply each month · typical year (5-yr pattern)</p></div>
<div class="card"><div class="relay">{relay}</div><div class="relay-key">{relay_legend}</div></div></section>

<section class="sec"><div class="shead"><h2>Where each origin sends its fruit</h2>
<p class="lede">2024 · % of their tonnage · includes the UK</p></div>
<div class="card">{sells}{rex}</div></section>

{world}

{market}

<footer class="foot">As-of dates vary by source: imports/re-exports through {month} (HMRC OTS, the latest
settled month, ~6–12 wks behind today); shelf this week (Trolley); world trade/production latest complete
year (UN Comtrade + FAOSTAT); UK production + wholesale (DEFRA). Auto-updates weekly ·
<a href="deep.html">full editorial view →</a> · generated {generated}.</footer>
</div></body></html>"""


_HUB = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Britain's Fruit Boards — the atlas</title>
<style>
 :root{{--ink:#241f1a;--accent:#5a3fb0;--mut:#7a7163;--card:#fdfbf7;--bg:#e8e1d3}}
 *{{box-sizing:border-box}}
 body{{margin:0;color:var(--ink);background:var(--bg);line-height:1.45;-webkit-font-smoothing:antialiased;
   font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
 .wrap{{max-width:760px;margin:0 auto;padding:56px 20px 100px}}
 .kick{{text-transform:uppercase;letter-spacing:.16em;font-size:.7rem;color:var(--accent);font-weight:700}}
 h1{{font-size:2.6rem;line-height:1.04;margin:.16em 0 .12em;letter-spacing:-.025em;font-weight:800}}
 .sub{{font-size:1rem;color:var(--mut);font-weight:500;margin:0 0 34px;max-width:48ch;line-height:1.5}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:16px}}
 .fcard{{display:flex;flex-direction:column;gap:7px;text-decoration:none;color:inherit;
   background:var(--card);border-radius:20px;padding:22px;
   box-shadow:0 1px 2px rgba(36,31,26,.05),0 16px 34px -20px rgba(36,31,26,.26);
   transition:transform .12s ease,box-shadow .12s ease}}
 .fcard:hover{{transform:translateY(-2px);box-shadow:0 2px 4px rgba(36,31,26,.06),0 22px 44px -20px rgba(36,31,26,.34)}}
 .femoji{{font-size:2rem;line-height:1}}
 .fname{{font-size:1.5rem;font-weight:800;letter-spacing:-.02em}}
 .fstat{{font-size:.84rem;color:var(--mut);font-weight:500;line-height:1.5}}
 .fstat b{{color:var(--accent);font-weight:700}}
 .foot{{margin-top:50px;font-size:.8rem;color:var(--mut);font-weight:500;line-height:1.7}}
 .foot a{{color:var(--accent)}}
</style></head><body><div class="wrap">
<div class="kick"><span aria-hidden="true">🇬🇧</span> free data · UK fresh-fruit trade</div>
<h1>Britain's Fruit Boards</h1>
<p class="sub">At-a-glance monthly boards for the UK fresh-fruit trade — who supplies Britain,
when, at what landed price, and where each sits in the world. One page per HS code.</p>
<div class="grid">{items}</div>
<div class="foot">{n} fruit{plural} · built from free data (HMRC · UN Comtrade · FAOSTAT · DEFRA · Trolley) ·
auto-updates weekly · generated {generated}.</div>
</div></body></html>"""


def _hub_card(fruit):
    """A summary card for the atlas hub (call with _FRUIT already set to `fruit`)."""
    s = _summary()
    cur, prev, rows, tot, mavg, mval = _board()
    top = rows[0]["origin"] if rows else "—"
    return {"slug": fruit.slug, "name": fruit.name, "emoji": fruit.emoji,
            "imports_kt": s["imports_kt"], "landed": s["avg"], "top": top}


def build_all():
    """Build one page per fruit in the registry, then the atlas hub. A fruit with
    missing data is skipped (so a fruit can be added before its data is fetched)."""
    cards = []
    for f in FRUITS.values():
        try:
            build(f)
            cards.append(_hub_card(f))
            print(f"built docs/{f.slug}.html")
        except Exception as exc:
            print(f"[build_board] skip {f.slug}: {type(exc).__name__}: {exc}")
    build_hub(cards)
    return cards


def build_hub(cards):
    items = "".join(
        f'<a class="fcard" href="{c["slug"]}.html">'
        f'<span class="femoji" aria-hidden="true">{c["emoji"]}</span>'
        f'<span class="fname">{c["name"]}</span>'
        f'<span class="fstat"><b>{c["imports_kt"]:.0f}K t</b> imports/yr · '
        f'top {c["top"]} · landed <b>£{c["landed"]:.2f}</b>/kg</span></a>'
        for c in cards)
    html = _HUB.format(items=items, n=len(cards), plural="" if len(cards) == 1 else "s",
                       generated=_dt.date.today().isoformat())
    out = REPO_ROOT / "docs" / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"built docs/index.html (atlas hub, {len(cards)} fruits)")
    return html


if __name__ == "__main__":
    build_all()
