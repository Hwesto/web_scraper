"""Render docs/index.html as a piece of data journalism about Britain's blueberries.

Not a trading terminal -- an editorial. The story is the year: who grows the fruit
Britain eats, when each origin lands, what it costs, and which varieties fill the
punnets. Charts are STATIC, custom-styled matplotlib (no default grey bars), embedded
as retina PNGs. The validated ~2-week nowcast edge is the closing proof, not the lede.

Reads only committed data (vintage store + data/weekly CSVs); the Monday cron
regenerates it. Run: python scripts/build_static_dashboard.py
"""
from __future__ import annotations

import base64
import datetime as _dt
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

from nowcast.backtest.within_month import calibrated_run
from nowcast.config import REPO_ROOT
from nowcast.market import asia_access, comtrade, netback, origin_prices
from nowcast.store import vintage

OUT = REPO_ROOT / "docs" / "index.html"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# --- editorial palette: blueberry skin -> warm contrast for the spring origins ---
INK = "#22202b"
SUBTLE = "#7a7686"
PAPER = "#ffffff"
ACCENT = "#5a3fb0"          # blueberry purple, the house colour
ORIGIN_COLOURS = {
    "Peru":         "#4c5fd5",   # indigo
    "Morocco":      "#e8833a",   # warm clementine (the spring hand-off)
    "South Africa": "#2a9d8f",   # teal
    "Chile":        "#6b3fa0",   # our focus berry, deep purple
    "Spain":        "#e9c46a",   # gold
    "Netherlands":  "#8d99ae",   # slate
    "Other":        "#d8d3cc",   # warm grey
}


def _style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 12.5,
        "text.color": INK,
        "axes.edgecolor": "#d9d5cf",
        "axes.labelcolor": SUBTLE,
        "xtick.color": SUBTLE,
        "ytick.color": SUBTLE,
        "axes.linewidth": 0.8,
        "figure.dpi": 200,
    })


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=PAPER, dpi=200)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _bare(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    if grid:
        ax.grid(axis=grid, color="#ece9e4", linewidth=1.0, zorder=0)
        ax.set_axisbelow(True)


# ----------------------------- data prep -----------------------------
def _load():
    vol = vintage.latest("hmrc_blueberry_imports").copy()
    vol["d"] = pd.to_datetime(vol["ref_period"]); vol["m"] = vol["d"].dt.month
    val = vintage.latest("hmrc_blueberry_import_value").copy()
    val["d"] = pd.to_datetime(val["ref_period"]); val["m"] = val["d"].dt.month
    prod = pd.read_csv(REPO_ROOT / "data" / "weekly" / "chile_uk_blueberry_by_producer.csv")
    return vol, val, prod


def _stats(vol, val):
    yr = vol.groupby(vol["d"].dt.year)["value"].sum()
    full = yr[(yr.index >= 2019) & (yr.index <= 2025)]
    latest_year = int(full.index.max())
    growth = (full.loc[2025] / full.loc[2019] - 1) * 100
    last12 = vol[vol["d"] >= vol["d"].max() - pd.DateOffset(months=11)]
    n_countries = vol[vol["d"] >= vol["d"].max() - pd.DateOffset(months=23)]["key"].nunique()
    v3 = val[val["d"] >= val["d"].max() - pd.DateOffset(months=35)]["value"].sum()
    t3 = vol[vol["d"] >= vol["d"].max() - pd.DateOffset(months=35)]["value"].sum() * 1000
    return dict(annual=full.loc[2025], growth=growth, countries=n_countries,
                avg_price=v3 / t3, latest_year=latest_year, last12_t=last12["value"].sum())


# ----------------------------- charts -----------------------------
def chart_relay(vol):
    """The hero: a stacked seasonal profile -- who lands each month of the year."""
    recent = vol[vol["d"] >= vol["d"].max() - pd.DateOffset(months=60)]
    ny = recent["d"].dt.year.nunique()
    top = (recent.groupby("key")["value"].sum().sort_values(ascending=False)
           .head(5).index.tolist())
    g = recent.copy(); g["k"] = g["key"].where(g["key"].isin(top), "Other")
    piv = (g.groupby(["m", "k"])["value"].sum().unstack(fill_value=0) / ny)
    piv = piv.reindex(index=range(1, 13), fill_value=0)
    order = top + ["Other"]
    piv = piv.reindex(columns=order, fill_value=0)

    fig, ax = plt.subplots(figsize=(9.2, 4.5))
    x = np.arange(12)
    base = np.zeros(12)
    for k in order:
        y = piv[k].values
        ax.fill_between(x, base, base + y, color=ORIGIN_COLOURS[k], linewidth=0,
                        zorder=2, label=k)
        base = base + y
    # label each band at its widest month, inside the band, nudged off the axes edges
    for k in order:
        y = piv[k].values
        if y.max() < 250:
            continue
        i = int(np.argmax(y))
        cum = piv[order].cumsum(axis=1)[k].values
        yc = cum[i] - y[i] / 2
        xpos, ha = i, "center"
        if i == 0:
            xpos, ha = 0.05, "left"
        elif i == 11:
            xpos, ha = 10.95, "right"
        ax.text(xpos, yc, k, ha=ha, va="center", fontsize=10.5, fontweight="bold",
                color="white" if k not in ("Spain", "Other") else INK, zorder=4)
    ax.set_xticks(x); ax.set_xticklabels(MONTHS)
    ax.set_xlim(0, 11)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    ax.set_ylabel("tonnes landed per month")
    _bare(ax)
    return _png(fig)


def chart_league(vol):
    """Origin league table -- share of the last 12 months."""
    last12 = vol[vol["d"] >= vol["d"].max() - pd.DateOffset(months=11)]
    sh = last12.groupby("key")["value"].sum().sort_values()
    sh = sh.tail(8)
    pct = sh / last12["value"].sum() * 100
    cols = [ORIGIN_COLOURS.get(k, ACCENT) for k in sh.index]
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    y = np.arange(len(sh))
    ax.barh(y, sh.values / 1000, color=cols, zorder=3, height=0.72)
    ax.set_yticks(y); ax.set_yticklabels(sh.index, fontsize=11.5, color=INK)
    for i, (t, p) in enumerate(zip(sh.values / 1000, pct.values)):
        ax.text(t + sh.max() / 1000 * 0.012, i, f"{t:,.0f}k t · {p:.0f}%",
                va="center", fontsize=10.5, color=SUBTLE)
    ax.set_xlim(0, sh.max() / 1000 * 1.18)
    ax.set_xlabel("thousand tonnes, last 12 months")
    _bare(ax, grid="x")
    return _png(fig)


def chart_price(vol, val, avg):
    """Average import price (£/kg) by calendar month, last 3 years."""
    v3 = val[val["d"] >= val["d"].max() - pd.DateOffset(months=35)]
    f3 = vol[vol["d"] >= vol["d"].max() - pd.DateOffset(months=35)]
    vm = v3.groupby("m")["value"].sum()
    fm = f3.groupby("m")["value"].sum() * 1000
    pk = (vm / fm).reindex(range(1, 13))
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    x = np.arange(12)
    ax.axhline(avg, color=SUBTLE, linestyle=(0, (4, 4)), linewidth=1.2, zorder=2)
    ax.text(11, avg, f"  3-yr avg £{avg:.2f}", va="bottom", ha="right",
            fontsize=10, color=SUBTLE)
    ax.plot(x, pk.values, color=ACCENT, linewidth=2.6, zorder=4)
    ax.fill_between(x, pk.values, avg, where=pk.values >= avg, color=ACCENT, alpha=0.10,
                    interpolate=True)
    ax.scatter(x, pk.values, s=42, color=ACCENT, zorder=5, edgecolor="white", linewidth=1.2)
    ax.set_xticks(x); ax.set_xticklabels(MONTHS)
    ax.set_xlim(-0.3, 12.2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"£{v:.1f}"))
    ax.set_ylabel("average import price per kg")
    _bare(ax)
    return _png(fig)


def chart_varieties(prod):
    """What Chile actually ships to Britain -- the cultivar mix."""
    cv = (prod.groupby("top_cultivar")["net_kg"].sum().sort_values()
          .replace(0, np.nan).dropna())
    cv = cv[cv.index.astype(str).str.strip() != ""]
    cv = cv.tail(8)
    total = prod["net_kg"].sum()
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    y = np.arange(len(cv))
    # purple gradient -- darkest for the biggest variety
    shades = plt.cm.Purples(np.linspace(0.45, 0.92, len(cv)))
    ax.barh(y, cv.values / 1e6, color=shades, zorder=3, height=0.72)
    ax.set_yticks(y)
    ax.set_yticklabels([c.title() for c in cv.index], fontsize=11.5, color=INK)
    for i, v in enumerate(cv.values):
        ax.text(v / 1e6 + cv.max() / 1e6 * 0.012, i, f"{v/total*100:.0f}%",
                va="center", fontsize=10.5, color=SUBTLE)
    ax.set_xlim(0, cv.max() / 1e6 * 1.16)
    ax.set_xlabel("million kg shipped to the UK (DUS customs records)")
    _bare(ax, grid="x")
    return _png(fig)


_REGION_COLOUR = {"Asia": "#6b3fa0", "Americas": "#e8833a", "Europe": "#4c5fd5",
                  "MiddleEast": "#2a9d8f", "SouthAmerica": "#8d99ae"}
_REGION_OF = netback._REGION


def chart_markets(t: pd.DataFrame):
    """Price-vs-volume map: where Chilean fruit nets most against how much it absorbs."""
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    for _, r in t.iterrows():
        reg = _REGION_OF.get(r["destination"], "Europe")
        size = min(r["net_kg"] / 1e6 * 11 + 50, 1700)
        ax.scatter(r["net_kg"] / 1e6, r["netback_usd_kg"], s=size,
                   color=_REGION_COLOUR.get(reg, "#8d99ae"), alpha=0.78,
                   edgecolor="white", linewidth=1.3, zorder=3)
    # label the markets that carry the story
    show = {"United States", "Netherlands", "South Korea", "United Kingdom",
            "China", "Germany", "Canada"}
    for _, r in t.iterrows():
        if r["destination"] in show:
            ax.annotate(r["destination"], (r["net_kg"] / 1e6, r["netback_usd_kg"]),
                        xytext=(0, 13), textcoords="offset points", ha="center",
                        fontsize=10, color=INK, fontweight="bold", zorder=4)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 1, 2, 5, 10, 20, 50])
    ax.get_xaxis().set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}k t"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:.0f}"))
    ax.set_xlabel("fruit the market absorbs  (thousand tonnes, log scale)")
    ax.set_ylabel("grower netback  ($/kg, after freight)")
    ax.margins(x=0.12, y=0.18)
    _bare(ax, grid="both")
    return _png(fig)


def chart_asia(top: pd.DataFrame):
    """Top China-approved producers, sized by the Asia-premium prize they can capture."""
    from nowcast.farm import names
    g = top.copy()
    g["label"] = g["producer"].map(names.canonicalize)      # fold cargo-text variants
    d = (g.groupby("label", as_index=False)["net_kg"].sum()
         .rename(columns={"label": "producer"}).sort_values("net_kg").tail(10))
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    y = np.arange(len(d))
    ax.barh(y, d["net_kg"] / 1e6, color="#6b3fa0", zorder=3, height=0.72)
    ax.set_yticks(y)
    ax.set_yticklabels([str(p).title() for p in d["producer"]], fontsize=11, color=INK)
    for i, kg in enumerate(d["net_kg"].values):
        ax.text(kg / 1e6 + d["net_kg"].max() / 1e6 * 0.012, i, f"{kg/1e6:.1f}M kg",
                va="center", fontsize=10, color=SUBTLE)
    ax.set_xlim(0, d["net_kg"].max() / 1e6 * 1.16)
    ax.set_xlabel("UK-bound volume of China-approved producers (million kg)")
    _bare(ax, grid="x")
    return _png(fig)


def chart_origin_wedge(w: pd.DataFrame):
    """Dumbbell: each origin's export price (FOB) -> UK landed price (CIF); gap = freight."""
    d = w.sort_values("net_kg").tail(8)
    fig, ax = plt.subplots(figsize=(9.2, 4.2))
    y = np.arange(len(d))
    for i, (_, r) in enumerate(d.iterrows()):
        ax.plot([r["fob_gbp_kg"], r["cif_gbp_kg"]], [i, i], color="#d9d4cc",
                linewidth=3, solid_capstyle="round", zorder=2)
    ax.scatter(d["fob_gbp_kg"], y, s=72, color=SUBTLE, zorder=3,
               label="origin export (FOB)")
    ax.scatter(d["cif_gbp_kg"], y, s=72, color=ACCENT, zorder=4,
               label="UK landed (CIF)")
    ax.set_yticks(y)
    ax.set_yticklabels(d["origin"], fontsize=11.5, color=INK)
    for i, (_, r) in enumerate(d.iterrows()):
        wg = r["wedge_gbp_kg"]
        tag = f"+£{wg:.2f}" if wg >= 0 else f"−£{abs(wg):.2f}"
        ax.text(max(r["fob_gbp_kg"], r["cif_gbp_kg"]) + 0.12, i, tag,
                va="center", fontsize=9.5, color=SUBTLE)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"£{v:.0f}"))
    ax.set_xlabel("price per kilo  (£)")
    ax.margins(x=0.16)
    ax.legend(loc="lower right", frameon=False, fontsize=9.5)
    _bare(ax, grid="x")
    return _png(fig)


def origin_wedge_block() -> str:
    """Per-origin FOB->CIF chapter -- empty until origin export prices are fetched."""
    w = origin_prices.wedge()
    if w.empty:
        return ""
    return _ORIGIN_TPL.format(chart=chart_origin_wedge(w), year=int(w["year"].iloc[0]))


def asia_access_block() -> str:
    """The phyto-access chapter -- empty until the SAG roster is fetched by the cron."""
    s = asia_access.summary()
    if not s.get("available"):
        return ""
    return _ASIA_TPL.format(
        chart=chart_asia(s["top_approved"]),
        premium=f"{s['asia_premium_usd_kg']:.2f}",
        n_approved=s["n_china_approved"], n_total=s["n_producers"],
        approved_share=f"{s['approved_kg_share_%']:.0f}")


# ----------------------------- assemble -----------------------------
def build() -> None:
    _style()
    vol, val, prod = _load()
    s = _stats(vol, val)
    cr = calibrated_run(); edge = cr["in_season"]["origin_nowcast"]
    n_calls = cr["in_season"]["n"]
    n_named = (prod["producer"].astype(str).str.strip() != "").sum()

    nb = netback.netback_table()
    nbi = nb.set_index("destination")
    mkt_year = comtrade.latest_year()
    top_mkt = nb.iloc[0]
    premium = (nbi.loc["South Korea", "netback_usd_kg"] /
               nbi.loc["United States", "netback_usd_kg"] - 1) * 100 \
        if {"South Korea", "United States"} <= set(nbi.index) else 0.0
    us_share = nbi.loc["United States", "vol_share_%"] if "United States" in nbi.index else 0.0

    html = _TPL.format(
        relay=chart_relay(vol),
        league=chart_league(vol),
        price=chart_price(vol, val, s["avg_price"]),
        varieties=chart_varieties(prod),
        markets=chart_markets(nb),
        origin_wedge=origin_wedge_block(),
        mkt_year=mkt_year,
        kr_premium=f"{premium:.0f}",
        us_share=f"{us_share:.0f}",
        top_netback=f"{top_mkt['netback_usd_kg']:.2f}",
        asia_access=asia_access_block(),
        annual_kt=f"{s['annual']/1000:,.0f}",
        countries=s["countries"],
        avg_price=f"{s['avg_price']:.2f}",
        growth=f"{s['growth']:.0f}",
        n_named=n_named,
        dir_skill=f"{edge['dir_skill_%']:.0f}",
        vs_naive=f"{edge['skill_vs_snaive_%']:.0f}",
        n_calls=n_calls,
        generated=_dt.datetime.utcnow().strftime("%-d %B %Y"),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html)//1024} KB)")


_TPL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Britain's Blueberry Year</title>
<style>
 :root{{--ink:#22202b;--subtle:#7a7686;--accent:#5a3fb0;--line:#e7e3dd}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:#faf8f5;color:var(--ink);
   font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.65}}
 .wrap{{max-width:760px;margin:0 auto;padding:56px 22px 80px}}
 .kicker{{text-transform:uppercase;letter-spacing:.18em;font-size:.72rem;font-weight:700;
   color:var(--accent);margin-bottom:14px}}
 h1{{font-family:Georgia,'Times New Roman',serif;font-size:2.9rem;line-height:1.08;
   font-weight:700;margin:0 0 18px;letter-spacing:-.01em}}
 .standfirst{{font-size:1.22rem;color:#494653;line-height:1.55;margin:0 0 26px;
   font-family:Georgia,serif}}
 .byline{{font-size:.82rem;color:var(--subtle);border-top:1px solid var(--line);
   border-bottom:1px solid var(--line);padding:12px 0;margin-bottom:40px}}
 h2{{font-family:Georgia,serif;font-size:1.7rem;font-weight:700;margin:52px 0 6px;
   letter-spacing:-.01em}}
 .deck{{color:var(--subtle);font-size:1rem;margin:0 0 18px}}
 p{{font-size:1.06rem;margin:0 0 18px}}
 figure{{margin:24px 0 8px}}
 figure img{{width:100%;display:block;border-radius:6px}}
 figcaption{{font-size:.82rem;color:var(--subtle);margin-top:10px;
   border-left:3px solid var(--line);padding-left:12px}}
 .stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);
   border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:8px 0 8px}}
 .stat{{background:#fff;padding:20px 14px;text-align:center}}
 .stat .n{{font-family:Georgia,serif;font-size:1.95rem;font-weight:700;color:var(--accent);
   line-height:1}}
 .stat .l{{font-size:.74rem;color:var(--subtle);margin-top:8px;line-height:1.3}}
 .edge{{background:#1d1a2e;color:#efeaff;border-radius:12px;padding:30px 30px 24px;
   margin:30px 0}}
 .edge h2{{color:#fff;margin-top:0}}
 .edge p{{color:#cfc8e6;font-size:1.02rem}}
 .edge .row{{display:flex;gap:26px;flex-wrap:wrap;margin-top:18px}}
 .edge .row div{{flex:1;min-width:120px}}
 .edge .big{{font-family:Georgia,serif;font-size:2.1rem;font-weight:700;color:#b9a4ff}}
 .edge .cap{{font-size:.78rem;color:#9a93b5;margin-top:2px}}
 .foot{{margin-top:54px;border-top:1px solid var(--line);padding-top:18px;
   font-size:.8rem;color:var(--subtle)}}
 .foot b{{color:#5b5766}}
 em{{color:var(--accent);font-style:normal;font-weight:600}}
 @media(max-width:560px){{h1{{font-size:2.1rem}}.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class="wrap">

<div class="kicker">🫐 The UK Fresh Blueberry Market</div>
<h1>Britain's blueberry year</h1>
<p class="standfirst">Britain eats blueberries every week of the year — yet almost
none are grown here in winter. Behind every punnet is a quiet global relay: a baton
passed from Peru to Morocco to South Africa to Chile and back, timed so the shelves
never go empty. Here is that year, in the data.</p>
<div class="byline">An automatic, self-updating read of HMRC trade records and Chilean
customs data · refreshed {generated}</div>

<div class="stats">
  <div class="stat"><div class="n">{annual_kt}k t</div><div class="l">imported in 2025</div></div>
  <div class="stat"><div class="n">{countries}</div><div class="l">source countries</div></div>
  <div class="stat"><div class="n">£{avg_price}</div><div class="l">average price per kg</div></div>
  <div class="stat"><div class="n">+{growth}%</div><div class="l">bigger than in 2019</div></div>
</div>

<h2>The relay</h2>
<p class="deck">Who lands when — average tonnes per month across recent years.</p>
<p>The year opens in the southern-hemisphere summer: <em>Chile</em> and <em>Peru</em>
carry January and February. As they fade, <em>Morocco</em> floods spring — its April
peak is the single biggest month any origin posts all year. A midsummer lull follows,
the one window when British and near-European fruit matters most. Then the baton swings
back across the equator: <em>Peru</em> and <em>South Africa</em> ramp hard through the
autumn to close the year.</p>
<figure><img src="{relay}" alt="Seasonal relay of UK blueberry imports by origin">
<figcaption>Average monthly arrivals by origin, last five years (HMRC, commodity
08104050). Bands are stacked — height is total fruit landing that month.</figcaption></figure>

<h2>Who supplies Britain</h2>
<p class="deck">Share of everything that landed in the last twelve months.</p>
<p>No single country owns the British blueberry. <em>Peru</em> and <em>Morocco</em> run
neck-and-neck at the top, together better than half the market; <em>South Africa</em>
is the clear third. Chile — the origin this project tracks weekly, fruit by fruit — is
smaller by tonnage but lands in the highest-value winter window.</p>
<figure><img src="{league}" alt="UK blueberry imports by country, last 12 months">
<figcaption>Twelve-month totals by origin (HMRC). Percentages are share of all
fresh-blueberry imports.</figcaption></figure>

<h2>What it costs</h2>
<p class="deck">Average import price per kilo, by month of the year.</p>
<p>The landed price of an imported kilo hovers around <em>£{avg_price}</em>, but it is
not flat. It firms in early autumn — September and October, as the southern season
restarts and air-freighted early fruit commands a premium — and softens through the
high-volume mid-winter and late-spring gluts. Price tracks scarcity, not the calendar.</p>
<figure><img src="{price}" alt="Average UK blueberry import price by month">
<figcaption>Import unit value = declared customs value ÷ tonnes, all origins (HMRC).
A proxy for the wholesale landed cost, not the supermarket shelf price.</figcaption></figure>

{origin_wedge}
<h2>What Chile ships</h2>
<p class="deck">The varieties inside Chile's punnets, by volume sent to the UK.</p>
<p>Chilean customs records name the cultivar on most shipments, so we can see exactly
which berries Britain buys. <em>Legacy</em> dominates — a firm, travel-hardy variety
bred for exactly this kind of six-week sea journey — followed by <em>Duke</em> and the
premium club varieties <em>Blue Ribbon</em> and <em>Draper</em>. Together they read
like a map of what survives the trip and still tastes of something on arrival.</p>
<figure><img src="{varieties}" alt="Chilean blueberry varieties shipped to the UK">
<figcaption>From {n_named} named Chilean exporters in the DUS customs feed. Cultivar is
declared on roughly half of shipments — this is the named subset.</figcaption></figure>

<h2>Where in the world to sell it</h2>
<p class="deck">Now flip the seat. You grow blueberries in Chile — where on Earth
does a kilo net you the most?</p>
<p>The same customs data, read the other way, prices every market Chile ships to.
After deducting ocean freight, a kilo sent to <em>South Korea</em> nets a Chilean
grower roughly <em>{kr_premium}% more</em> than the same kilo sent to the United
States — and the premium survives the longer, dearer voyage. Japan and the smaller
Asian markets pay more still. Yet the United States alone takes <em>{us_share}%</em>
of all Chilean fruit, because the premium lanes are tiny: Korea and Japan together
can't absorb what one week of the US season ships. Holland looks cheap, but it is a
re-export hub — a distribution valve, not a final table.</p>
<p>So "where to sell" is never one answer. It is a portfolio: your firmest, certified,
earliest fruit chases the Asian premium (where transit and phytosanitary rules let in
only the best); the bulk clears through the US; Europe absorbs the rest. The one storm
cloud is a 2025 US import tariff that Chilean blueberries were <em>not</em> exempted
from — a levy landing squarely on that 40%-of-volume lane.</p>
<figure><img src="{markets}" alt="Chilean blueberry netback by destination market">
<figcaption>Each bubble is a destination ({mkt_year}); height is grower netback per kg
after freight, width of the chart is how much fruit the market absorbs (log scale),
bubble size is total value. Prices and volumes observed (UN Comtrade, HS 081040);
freight derived from 40ft-reefer rates ÷ ~11 t blueberry payload (documented, tunable).</figcaption></figure>

{asia_access}
<div class="edge">
<h2>How we know what's coming — two weeks early</h2>
<p>This is the working edge behind the journalism. Chile's export records publish
weeks before Britain's official import figures. By transit-shifting the outbound
shipments, we estimate each month's Chilean arrivals <em style="color:#b9a4ff">about
two weeks before HMRC prints them</em> — and the call is more accurate than simply
assuming "same as last year".</p>
<div class="row">
  <div><div class="big">~2 wks</div><div class="cap">ahead of the official figure</div></div>
  <div><div class="big">{dir_skill}%</div><div class="cap">got the direction right</div></div>
  <div><div class="big">+{vs_naive}%</div><div class="cap">more accurate than the naive baseline</div></div>
  <div><div class="big">{n_calls}</div><div class="cap">in-season calls back-tested</div></div>
</div>
</div>

<div class="foot">
<b>Sources & honesty.</b> Volumes and prices: HMRC Overseas Trade Statistics (fresh
blueberries, 08104050), reconciled across vintages. Chilean detail: Aduana DUS customs
export records via datos.gob.cl. The two-week edge is validated out-of-sample on the
deep-sea Chilean lane only; the whole-market view is HMRC-anchored. Deliberately not
claimed: UK retail-shelf price direction (does not back-test) and named certified
orchard mapping (requires paid registries). The discipline is the product.
</div>
</div></body></html>"""


_ORIGIN_TPL = """
<h2>What every origin charges — and the freight wedge</h2>
<p class="deck">Two prices per supplier: what the fruit costs leaving its own country
(FOB) and what it's worth landed in Britain (CIF). The gap is mostly ocean freight.</p>
<p>Same fruit, two ends of the journey. The grey dot is each origin's own export price;
the purple dot is what Britain pays for it at the border ({year}). The distance between
them is the freight-and-insurance wedge — wide for the deep-sea origins (Chile, South
Africa, Argentina ride ~£0.5–1.6/kg of shipping), barely there for short-haul Europe
(Spain ≈ £0). Where the wedge goes <em>negative</em> the country is a re-export hub, not
a true grower — Dutch and Portuguese "exports" are largely fruit landed elsewhere first,
so their FOB sits above the UK border price. A clean tell for which origins actually
grow what they ship.</p>
<figure><img src="{chart}" alt="Origin export price vs UK landed price, by country">
<figcaption>Origin export FOB (UN Comtrade, reporter=origin, HS 081040) vs UK-landed CIF
(HMRC, value÷volume), {year}, USD→GBP at a single notional rate. Annual; Comtrade
reporter coverage lags, so some origins are absent in the latest year.</figcaption></figure>
"""


_ASIA_TPL = """
<h2>Who can actually chase the premium</h2>
<p class="deck">The best price means nothing if your fruit can't get in. China only
admits SAG-registered orchards — so which of our named producers are cleared?</p>
<p>Matching our named Chilean exporters against the SAG roster of orchards authorised
for China, <em>{n_approved} of {n_total}</em> producers in our flow are cleared —
covering <em>{approved_share}%</em> of the UK-bound volume we can name. Those are the
growers positioned to steer fruit toward the <em>${premium}/kg</em> premium that Asia
nets over the US bulk lane. The rest are locked to the Atlantic markets until they
clear registration.</p>
<figure><img src="{chart}" alt="China-approved Chilean blueberry producers in our flow">
<figcaption>Named producers matched to the SAG China-authorised orchard roster, by
UK-bound volume. Roster: SAG "Listado de predios de arándanos a China"; match is
name-canonicalised, so it is the high-confidence overlap, not the full register.</figcaption></figure>
"""


if __name__ == "__main__":
    build()
