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

from deep.backtest.within_month import calibrated_run
from deep.config import REPO_ROOT
from deep import price
from deep.market import asia_access, comtrade, fx, netback, origin_prices
from deep.store import vintage

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


def chart_origin_season(vol, origin):
    """An origin's UK arrival profile -- avg tonnes/month, peak months highlighted."""
    pv = vol[vol["key"] == origin].copy()
    ny = max(1, pv["d"].dt.year.nunique())
    prof = pv.groupby("m")["value"].sum().reindex(range(1, 13), fill_value=0) / ny
    base = ORIGIN_COLOURS.get(origin, ACCENT)
    peak = prof.max() * 0.5
    cols = [base if prof[m] >= peak else "#d8d3cc" for m in range(1, 13)]
    fig, ax = plt.subplots(figsize=(9.2, 3.6))
    x = np.arange(12)
    ax.bar(x, prof.values, color=cols, zorder=3, width=0.72)
    ax.set_xticks(x); ax.set_xticklabels(MONTHS)
    step = 1000 if prof.max() < 8000 else 2000
    ax.set_yticks(np.arange(0, prof.values.max() + step, step))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    ax.set_ylabel("avg tonnes landed per month")
    _bare(ax)
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
            "China", "Germany", "Canada", "Hong Kong", "Singapore"}
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


def chart_peru_outlook(f: pd.DataFrame):
    """Peru fresh-export trajectory, split US vs rest, with USDA forecast years faded."""
    f = f.sort_values("season").reset_index(drop=True)
    us = f["exports_us_mt"] / 1000
    row = (f["exports_mt"] - f["exports_us_mt"]) / 1000
    fc = f["status"].eq("forecast").values
    x = np.arange(len(f))
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    for i in range(len(f)):
        a = 0.5 if fc[i] else 1.0
        ax.bar(x[i], us.iloc[i], color="#e8833a", alpha=a, zorder=3, width=0.72)
        ax.bar(x[i], row.iloc[i], bottom=us.iloc[i], color="#b9a9d6", alpha=a,
               zorder=3, width=0.72)
        ax.text(x[i], f["exports_mt"].iloc[i] / 1000 + 4,
                f"{f['exports_us_share_%'].iloc[i]:.0f}%", ha="center",
                fontsize=8.5, color=SUBTLE)
    ax.set_xticks(x); ax.set_xticklabels(f["season"], fontsize=10, color=INK)
    ax.set_ylabel("fresh exports (000 t)")
    ax.bar(0, 0, color="#e8833a", label="to USA")
    ax.bar(0, 0, color="#b9a9d6", label="rest of world")
    ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    ax.text(x[fc.argmax()] - 0.4, ax.get_ylim()[1] * 0.02, "USDA forecast →",
            fontsize=8.5, color=SUBTLE, style="italic") if fc.any() else None
    _bare(ax, grid="y")
    return _png(fig)


def chart_asia(top: pd.DataFrame):
    """Top China-approved producers, sized by the Asia-premium prize they can capture."""
    from deep.farm import names
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


def _ink_or_white(c):
    """Readable label colour for a segment fill (by luminance)."""
    import matplotlib.colors as mcolors
    r, g, b = mcolors.to_rgb(c)
    return INK if 0.299 * r + 0.587 * g + 0.114 * b > 0.6 else "white"


def _top_share(s: pd.Series, n: int = 6) -> pd.Series:
    """Normalise to shares, keep the top n, fold the rest into 'Other'."""
    s = s[s > 0].sort_values(ascending=False)
    s = s / s.sum()
    if len(s) > n:
        s = pd.concat([s.head(n), pd.Series({"Other": s.iloc[n:].sum()})])
    return s


def chart_shelf(vol, prod):
    """What's offered now: current origin mix (HMRC, latest month) + Chile's variety split."""
    cur = vol[vol["d"] == vol["d"].max()]
    origins = _top_share(cur.groupby("key")["value"].sum())
    cv = prod.copy(); cv["top_cultivar"] = cv["top_cultivar"].astype(str).str.strip()
    varieties = _top_share(cv[cv["top_cultivar"] != ""].groupby("top_cultivar")["net_kg"].sum())
    vidx = list(varieties.index)
    vshade = {n: plt.cm.Purples(0.45 + 0.5 * (i / max(1, len(vidx) - 1)))
              for i, n in enumerate(vidx)}

    fig, ax = plt.subplots(figsize=(9.2, 2.9))

    def stack(yy, series, colour):
        left = 0.0
        for name, frac in series.items():
            c = colour(name)
            ax.barh(yy, frac, left=left, height=0.6, color=c, edgecolor="white",
                    linewidth=1.4, zorder=3)
            label = (f"{str(name).title()}\n{frac*100:.0f}%" if frac > 0.12
                     else (f"{frac*100:.0f}%" if frac > 0.05 else ""))
            if label:
                ax.text(left + frac / 2, yy, label, ha="center", va="center",
                        fontsize=8.5, fontweight="bold", color=_ink_or_white(c))
            left += frac

    stack(1, origins, lambda n: ORIGIN_COLOURS.get(n, "#b9b3aa"))
    stack(0, varieties, lambda n: vshade.get(n, "#cccccc"))
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Chile's\nvarieties", "On shelf\nby origin"],
                       fontsize=10.5, color=INK)
    ax.set_xlim(0, 1); ax.set_ylim(-0.55, 1.55); ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    return _png(fig)


_RENEWAL_COHORTS = ["≤2010", "2011–15", "2016–19", "2020–23", "2024+"]
_RENEWAL_COLS = ["#cfcabf", "#b9a9d6", "#9a78c0", "#7a4fb0", "#4a2f96"]   # old grey → new purple


def chart_renewal(cat: pd.DataFrame):
    """What Chile is planting: hectares by variety, split by planting period (renewal)."""
    cat = cat[cat["hectares"].notna() & cat["planting_year"].notna()].copy()
    cat["cohort"] = pd.cut(cat["planting_year"], bins=[0, 2010, 2015, 2019, 2023, 2100],
                           labels=_RENEWAL_COHORTS)
    top = cat.groupby("variedad")["hectares"].sum().sort_values().tail(7)
    piv = (cat[cat["variedad"].isin(top.index)]
           .pivot_table(index="variedad", columns="cohort", values="hectares",
                        aggfunc="sum", observed=False).reindex(top.index).fillna(0))
    fig, ax = plt.subplots(figsize=(9.2, 4.1))
    y = np.arange(len(top)); left = np.zeros(len(top))
    for c, col in zip(_RENEWAL_COHORTS, _RENEWAL_COLS):
        vals = piv[c].values
        ax.barh(y, vals, left=left, color=col, height=0.72, zorder=3, label=c)
        left += vals
    ax.set_yticks(y)
    ax.set_yticklabels([str(v).title() for v in top.index], fontsize=11.5, color=INK)
    ax.set_xlabel("hectares planted (Catastro Frutícola), coloured by planting period")
    ax.legend(title="planted", ncol=5, fontsize=8.5, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.18), columnspacing=1.1)
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


def origin_uk_block(vol, origin: str) -> str:
    """Generic <origin>→UK block: arrival seasonality + landed/FOB price, from held data.
    Returns "" if we have no UK volume for the origin (keeps the cell honestly empty)."""
    pv = vol[vol["key"] == origin]
    if pv.empty or pv["value"].sum() <= 0:
        return ""
    ny = max(1, pv["d"].dt.year.nunique())
    prof = pv.groupby("m")["value"].sum() / ny
    peak_month = MONTHS[int(prof.idxmax()) - 1]

    cif = price.import_unit_value(origin).dropna()
    cif_recent = (cif[cif.index >= cif.index.max() - pd.DateOffset(months=11)].mean()
                  if len(cif) else float("nan"))
    pr = origin_prices.load()
    pr = pr[(pr["origin"] == origin) & (pr["dest"] == "United Kingdom")].sort_values("year")

    price_line, fob_cap = "", ""
    if pd.notna(cif_recent):
        price_line = f"It lands at about <em>£{cif_recent:.2f}/kg</em> CIF"
        if len(pr):
            fob = float(pr["fob_usd_kg"].iloc[-1]); yr = int(pr["year"].iloc[-1])
            wedge = cif_recent - fob * fx.gbp_per_usd()
            price_line += (f", from an export price near <em>${fob:.2f}/kg</em> FOB "
                           f"({yr}) — a freight wedge of about <em>£{wedge:.2f}/kg</em>")
            fob_cap = f"Export FOB: UN Comtrade {origin}→UK {yr} (${fob:.2f}/kg); "
        price_line += "."
    return f"""
<h2>{origin} → Britain</h2>
<p class="deck">When {origin} supplies British shelves, and at what price.</p>
<p>{origin}'s arrivals into the UK peak around <em>{peak_month}</em>. {price_line}</p>
<figure><img src="{chart_origin_season(vol, origin)}" alt="{origin} blueberry arrivals into the UK by month">
<figcaption>Average monthly {origin} arrivals (HMRC, 08104050), peak months highlighted.
{fob_cap}landed CIF: HMRC {origin} unit value, last 12 months.</figcaption></figure>"""


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
# Vocabulary for the two selectors. Adding a new exporter/importer is just a
# string here plus block(s) tagged to it; empty cells show honestly in the matrix.
EXPORTERS = ["Global", "Chile", "Peru", "Morocco", "South Africa", "Spain", "Netherlands"]
IMPORTERS = ["Global", "UK", "US", "China", "Netherlands"]
DEFAULT = ("Global", "UK")


def _section(b: dict) -> str:
    """One comparison block, tagged with its (exporter,importer) pair + source."""
    return (f'<section class="block" data-pair="{b["exp"]}|{b["imp"]}">'
            f'<div class="src"><span class="pair">{b["exp"]} → {b["imp"]}</span>'
            f'<span class="feed">{b["source"]}</span></div>{b["body"]}</section>')


def _matrix(blocks: list[dict]) -> str:
    """Coverage grid: per (exporter,importer) cell, how many blocks/sources we hold."""
    cov: dict[tuple[str, str], list[str]] = {}
    for b in blocks:
        cov.setdefault((b["exp"], b["imp"]), []).append(b["source"])
    head = "".join(f"<th>{i}</th>" for i in IMPORTERS)
    rows = ""
    for e in EXPORTERS:
        cells = ""
        for i in IMPORTERS:
            srcs = cov.get((e, i), [])
            klass = "cell filled" if srcs else "cell empty"
            label = f'<b>{len(srcs)}</b>' if srcs else "·"
            tip = " · ".join(sorted(set(srcs))) if srcs else "no source yet"
            cells += (f'<td class="{klass}" data-pair="{e}|{i}" title="{tip}" '
                      f'onclick="pick(\'{e}\',\'{i}\')">{label}</td>')
        rows += f'<tr><th>{e}</th>{cells}</tr>'
    return (f'<table id="matrix"><tr><th class="corner">exp · imp</th>{head}</tr>'
            f'{rows}</table>')


def _controls() -> str:
    def opts(vals):
        return "".join(f'<option value="{v}">{v}</option>' for v in vals)
    return (f'<div class="controls">'
            f'<label>Exporter<select id="exp">{opts(EXPORTERS)}</select></label>'
            f'<label>Importer<select id="imp">{opts(IMPORTERS)}</select></label>'
            f'<span id="crumb"></span></div>')


def build() -> None:
    _style()
    vol, val, prod = _load()
    s = _stats(vol, val)
    cr = calibrated_run(); edge = cr["in_season"]["origin_nowcast"]
    n_calls = cr["in_season"]["n"]
    n_named = (prod["producer"].astype(str).str.strip() != "").sum()

    nb = netback.netback_table(); nbi = nb.set_index("destination")
    mkt_year = comtrade.latest_year()
    premium = (nbi.loc["South Korea", "netback_usd_kg"] /
               nbi.loc["United States", "netback_usd_kg"] - 1) * 100 \
        if {"South Korea", "United States"} <= set(nbi.index) else 0.0
    us_share = nbi.loc["United States", "vol_share_%"] if "United States" in nbi.index else 0.0

    blocks: list[dict] = []

    def add(exp, imp, source, body):
        if body and body.strip():
            blocks.append({"exp": exp, "imp": imp, "source": source, "body": body})

    add("Global", "UK", "HMRC OTS", f"""
<h2>The relay</h2>
<p class="deck">Who lands when — average tonnes per month across recent years.</p>
<p>The year opens in the southern-hemisphere summer: <em>Chile</em> and <em>Peru</em>
carry January and February. As they fade, <em>Morocco</em> floods spring — its April
peak is the single biggest month any origin posts all year. A midsummer lull follows,
the one window when British and near-European fruit matters most. Then the baton swings
back across the equator: <em>Peru</em> and <em>South Africa</em> ramp hard through the
autumn to close the year.</p>
<figure><img src="{chart_relay(vol)}" alt="Seasonal relay of UK blueberry imports by origin">
<figcaption>Average monthly arrivals by origin, last five years (HMRC, commodity
08104050). Bands are stacked — height is total fruit landing that month.</figcaption></figure>""")

    add("Global", "UK", "HMRC OTS", f"""
<h2>Who supplies Britain</h2>
<p class="deck">Share of everything that landed in the last twelve months.</p>
<p>No single country owns the British blueberry. <em>Peru</em> and <em>Morocco</em> run
neck-and-neck at the top, together better than half the market; <em>South Africa</em>
is the clear third. Chile — the origin this project tracks weekly, fruit by fruit — is
smaller by tonnage but lands in the highest-value winter window.</p>
<figure><img src="{chart_league(vol)}" alt="UK blueberry imports by country, last 12 months">
<figcaption>Twelve-month totals by origin (HMRC). Percentages are share of all
fresh-blueberry imports.</figcaption></figure>""")

    add("Global", "UK", "HMRC + Chile DUS", f"""
<h2>What's on Britain's shelves now</h2>
<p class="deck">The shelf labels neither origin nor variety — but the import flow does.
This is the mix landing right now, and the cultivars inside Chile's share.</p>
<p>A UK punnet carries no cultivar and a rotating, often-unlabelled origin, so "what's
offered" can't be read off the shelf — you read it off the customs flow. The upper bar
is the origin mix of fruit landing in the latest month (<em>{vol['d'].max().strftime('%B %Y')}</em>),
the relay's current hand; the lower bar is the cultivar split <em>within</em> Chile's
shipments — <em>Legacy</em> leads, then <em>Duke</em>, with premium <em>Blue Ribbon</em>
and <em>Draper</em> behind — the only stage where variety is ever recorded.</p>
<figure><img src="{chart_shelf(vol, prod)}" alt="Current UK blueberry mix by origin and Chile's variety split">
<figcaption>Origin: HMRC imports, latest available month ({vol['d'].max().strftime('%B %Y')}).
Variety: Chilean DUS cultivar share of named shipments (Chile's slice, when in season —
not necessarily this month's shelf). A supply-side proxy; UK retail discloses neither.</figcaption></figure>""")

    add("Global", "UK", "HMRC OTS", f"""
<h2>What it costs</h2>
<p class="deck">Average import price per kilo, by month of the year.</p>
<p>The landed price of an imported kilo hovers around <em>£{s['avg_price']:.2f}</em>, but
it is not flat. It firms in early autumn — as the southern season restarts and
air-freighted early fruit commands a premium — and softens through the high-volume
mid-winter and late-spring gluts. Price tracks scarcity, not the calendar.</p>
<figure><img src="{chart_price(vol, val, s['avg_price'])}" alt="Average UK blueberry import price by month">
<figcaption>Import unit value = declared customs value ÷ tonnes, all origins (HMRC).
A proxy for the wholesale landed cost, not the supermarket shelf price.</figcaption></figure>""")

    add("Global", "UK", "Comtrade + HMRC", origin_wedge_block())

    add("Chile", "UK", "Chile DUS customs", f"""
<h2>What Chile ships</h2>
<p class="deck">The varieties inside Chile's punnets, by volume sent to the UK.</p>
<p>Chilean customs records name the cultivar on most shipments, so we can see exactly
which berries Britain buys. <em>Legacy</em> dominates — a firm, travel-hardy variety
bred for exactly this kind of six-week sea journey — followed by <em>Duke</em> and the
premium club varieties <em>Blue Ribbon</em> and <em>Draper</em>.</p>
<figure><img src="{chart_varieties(prod)}" alt="Chilean blueberry varieties shipped to the UK">
<figcaption>From {n_named} named Chilean exporters in the DUS customs feed. Cultivar is
declared on roughly half of shipments — this is the named subset.</figcaption></figure>""")

    import glob as _glob
    _catf = _glob.glob(str(REPO_ROOT / "data" / "farm" / "*catastro*.parquet"))
    if _catf:
        cat = pd.read_parquet(_catf[0])
        add("Chile", "UK", "Catastro Frutícola", f"""
<h2>What Chile is planting next</h2>
<p class="deck">The orchard census, read by planting year — which varieties Chile is
putting in the ground, and which it's quietly abandoning.</p>
<p>Today's punnet is yesterday's planting decision, so the census is a forward look. The
old workhorses are <em>aging out</em>: <em>Legacy</em> and <em>Duke</em> still dominate the
ground, but almost none has been planted since 2019, and <em>Brigitta</em>/<em>Elliot</em>
are pure legacy. The replant is going to the premium club varieties — <em>Blue Ribbon</em>
barely existed before 2010 and is now the standout of recent plantings, with
<em>Suziblue</em> and <em>Top Shelf</em> behind. As those young blocks reach full bearing,
the mix Britain buys will tilt the same way — better-travelling, higher-value fruit, the
move Chile is making to answer Peru.</p>
<figure><img src="{chart_renewal(cat)}" alt="Chilean blueberry hectares by variety and planting period">
<figcaption>Hectares by variety, coloured by planting period (CIREN-ODEPA Catastro
Frutícola, latest survey per region). Grey = old plantings, purple = recent — the colour
shift down each bar is the renewal. Area, not yield; young blocks bear little yet.</figcaption></figure>""")

    add("Chile", "Global", "UN Comtrade", f"""
<h2>Where in the world to sell it</h2>
<p class="deck">Flip the seat. You grow in Chile — where does a kilo net the most?</p>
<p>The same customs data, read the other way, prices every market Chile ships to. After
deducting ocean freight, a kilo sent to <em>South Korea</em> nets a grower roughly
<em>{premium:.0f}% more</em> than the same kilo into the United States — and the premium
survives the longer voyage. Yet the US alone takes <em>{us_share:.0f}%</em> of Chilean
fruit, because the premium lanes are tiny. Holland looks cheap, but it is a re-export
hub — a distribution valve, not a final table.</p>
<figure><img src="{chart_markets(nb)}" alt="Chilean blueberry netback by destination market">
<figcaption>Each bubble is a destination ({mkt_year}); height is grower netback per kg
after freight, width is how much the market absorbs (log scale), bubble size is total
value. Observed (UN Comtrade, HS 081040); freight from reefer rate ÷ ~11 t payload.</figcaption></figure>""")

    nb_peru = netback.netback_table(origin="Peru")
    if not nb_peru.empty:
        pe = nb_peru.set_index("destination")
        us_sh = pe.loc["United States", "vol_share_%"] if "United States" in pe.index else 0
        nl_sh = pe.loc["Netherlands", "vol_share_%"] if "Netherlands" in pe.index else 0
        peru_year = comtrade.latest_year(comtrade.load(comtrade.PERU_CACHE))
        add("Peru", "Global", "UN Comtrade", f"""
<h2>Where Peru sells — and its one big risk</h2>
<p class="deck">The same lens on the world's #1 exporter. Peru ships ~360k t a season —
but to a far narrower set of tables than Chile.</p>
<p>Peru's reach is strikingly concentrated: the <em>United States</em> alone takes about
<em>{us_sh:.0f}%</em> of its blueberries, and the <em>Netherlands</em> — Europe's
re-export valve — another <em>{nl_sh:.0f}%</em>. Asia is still a small slice but the
fastest-growing: Hong Kong, China, Singapore and India all jumped double- or triple-digit
year on year. The flip side of dominance is exposure — over half the crop rides one
destination, so a US price wobble or trade-policy shift lands harder on Peru than on
anyone, Chile included.</p>
<figure><img src="{chart_markets(nb_peru)}" alt="Peru blueberry netback by destination market">
<figcaption>Each bubble a destination ({peru_year}); height is netback per kg after freight,
width is volume absorbed (log scale). UN Comtrade reporter=Peru, HS 081040; freight =
deep-sea reefer ÷ payload (ex-Callao transit, a touch shorter than Chile).</figcaption></figure>""")

    _peruf = REPO_ROOT / "data" / "market" / "peru_fundamentals.csv"
    if _peruf.exists():
        pf = pd.read_csv(_peruf)
        cur = pf[pf["status"] == "forecast"].iloc[0] if (pf["status"] == "forecast").any() else pf.iloc[-1]
        add("Peru", "Global", "USDA-FAS", f"""
<h2>Peru's supply outlook</h2>
<p class="deck">Peru has no orchard census like Chile's — so the USDA's annual estimate
is the structural and forward view: how much is planted, picked, and shipped, two
seasons out.</p>
<p>The trajectory is relentless: harvested area near <em>{int(cur['area_ha']):,} ha</em>
and production forecast to a record <em>{int(cur['production_mt']/1000)}k t</em> in
{cur['season']}, with exports around <em>{int(cur['exports_mt']/1000)}k t</em>. The
striking part is the constancy of the concentration — the United States has taken
~54–56% of Peru's fruit every year, and the USDA forecast has that share edging
<em>up</em> to {cur['exports_us_share_%']:.0f}%. Peru isn't diversifying away from its
one big customer; it's doubling down while Asia grows underneath.</p>
<figure><img src="{chart_peru_outlook(pf)}" alt="Peru blueberry export outlook, US vs rest of world">
<figcaption>Fresh exports by marketing year, split US vs rest (USDA-FAS Blueberry
Annual, Lima; faded bars + % are FAS estimates/forecasts). Peru's substitute for an
orchard census — authoritative annual estimates, not a per-block survey.</figcaption></figure>""")

    # Per-origin <origin>→UK blocks, all from held data (HMRC seasonality + CIF,
    # Comtrade FOB). Lights up a matrix cell per major supplier; empties stay empty.
    for origin in ["Peru", "Morocco", "South Africa", "Spain", "Netherlands"]:
        add(origin, "UK", "HMRC + Comtrade", origin_uk_block(vol, origin))

    add("Chile", "China", "SAG + Comtrade", asia_access_block())

    add("Chile", "UK", "HMRC + DUS · model", f"""
<div class="edge">
<h2>How we know what's coming — two weeks early</h2>
<p>Chile's export records publish weeks before Britain's official import figures. By
transit-shifting the outbound shipments, we estimate each month's Chilean arrivals
<em style="color:#b9a4ff">about two weeks before HMRC prints them</em> — and the call
beats simply assuming "same as last year".</p>
<div class="row">
  <div><div class="big">~2 wks</div><div class="cap">ahead of the official figure</div></div>
  <div><div class="big">{edge['dir_skill_%']:.0f}%</div><div class="cap">got the direction right</div></div>
  <div><div class="big">+{edge['skill_vs_snaive_%']:.0f}%</div><div class="cap">better than the naive baseline</div></div>
  <div><div class="big">{n_calls}</div><div class="cap">in-season calls back-tested</div></div>
</div></div>""")

    html = _PAGE.format(
        controls=_controls(), matrix=_matrix(blocks),
        blocks="\n".join(_section(b) for b in blocks),
        default_exp=DEFAULT[0], default_imp=DEFAULT[1],
        annual_kt=f"{s['annual']/1000:,.0f}", countries=s["countries"],
        avg_price=f"{s['avg_price']:.2f}", growth=f"{s['growth']:.0f}",
        generated=_dt.datetime.utcnow().strftime("%-d %B %Y"),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html)//1024} KB, {len(blocks)} blocks)")


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
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
   border-bottom:1px solid var(--line);padding:12px 0;margin-bottom:28px}}
 h2{{font-family:Georgia,serif;font-size:1.7rem;font-weight:700;margin:14px 0 6px;
   letter-spacing:-.01em}}
 .deck{{color:var(--subtle);font-size:1rem;margin:0 0 18px}}
 p{{font-size:1.06rem;margin:0 0 18px}}
 figure{{margin:24px 0 8px}}
 figure img{{width:100%;display:block;border-radius:6px}}
 figcaption{{font-size:.82rem;color:var(--subtle);margin-top:10px;
   border-left:3px solid var(--line);padding-left:12px}}
 .stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);
   border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:8px 0 26px}}
 .stat{{background:#fff;padding:20px 14px;text-align:center}}
 .stat .n{{font-family:Georgia,serif;font-size:1.95rem;font-weight:700;color:var(--accent);
   line-height:1}}
 .stat .l{{font-size:.74rem;color:var(--subtle);margin-top:8px;line-height:1.3}}
 .controls{{display:flex;gap:18px;align-items:flex-end;flex-wrap:wrap;margin:8px 0 14px}}
 .controls label{{display:flex;flex-direction:column;gap:6px;font-size:.7rem;font-weight:700;
   text-transform:uppercase;letter-spacing:.12em;color:var(--subtle)}}
 .controls select{{font-size:1rem;padding:8px 10px;border:1px solid var(--line);
   border-radius:8px;background:#fff;color:var(--ink);font-family:inherit;min-width:150px}}
 #crumb{{margin-left:auto;font-family:Georgia,serif;font-size:1.05rem;font-weight:700;
   color:var(--accent)}}
 .mxnote{{font-size:.78rem;color:var(--subtle);margin:0 0 6px}}
 #matrix{{border-collapse:collapse;width:100%;margin:0 0 8px;font-size:.85rem}}
 #matrix th,#matrix td{{border:1px solid var(--line);padding:9px 6px;text-align:center}}
 #matrix th{{color:var(--subtle);font-weight:600;background:#fff}}
 #matrix .corner{{font-size:.62rem;text-transform:uppercase;letter-spacing:.06em}}
 #matrix td.cell{{cursor:pointer;background:#fff}}
 #matrix td.filled{{background:#efeafc;color:var(--accent);font-weight:700}}
 #matrix td.empty{{color:#cfcabf}}
 #matrix td.sel{{outline:3px solid var(--accent);outline-offset:-3px}}
 .block{{border-top:1px solid var(--line);padding-top:8px;margin-top:30px}}
 .block .src{{display:flex;gap:10px;align-items:center;margin:6px 0 2px;font-size:.72rem}}
 .block .src .pair{{background:var(--accent);color:#fff;padding:2px 10px;border-radius:20px;
   font-weight:700;letter-spacing:.03em}}
 .block .src .feed{{color:var(--subtle);text-transform:uppercase;letter-spacing:.1em;
   font-weight:700}}
 #empty{{color:var(--subtle);font-style:italic;padding:34px 0;font-size:1.02rem}}
 .edge{{background:#1d1a2e;color:#efeaff;border-radius:12px;padding:30px 30px 24px;
   margin:14px 0}}
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
 @media(max-width:560px){{h1{{font-size:2.1rem}}.stats{{grid-template-columns:repeat(2,1fr)}}
   #crumb{{margin-left:0;width:100%}}}}
</style></head><body><div class="wrap">

<div class="kicker">🫐 The UK Fresh Blueberry Market</div>
<h1>Britain's blueberry year</h1>
<p class="standfirst">Britain eats blueberries every week of the year — yet almost
none are grown here in winter. Behind every punnet is a quiet global relay. Pick an
<em>exporter</em> and an <em>importer</em> below to read that trade from either seat.</p>
<div class="byline">An automatic, self-updating read of HMRC trade records and Chilean
customs data · refreshed {generated}</div>

<div class="stats">
  <div class="stat"><div class="n">{annual_kt}k t</div><div class="l">imported in 2025</div></div>
  <div class="stat"><div class="n">{countries}</div><div class="l">source countries</div></div>
  <div class="stat"><div class="n">£{avg_price}</div><div class="l">average price per kg</div></div>
  <div class="stat"><div class="n">+{growth}%</div><div class="l">bigger than in 2019</div></div>
</div>

{controls}
<p class="mxnote">Coverage — each cell is how many data blocks we hold for that
exporter→importer pair (click to jump). Empty cells are honest gaps, filled as new
sources come online.</p>
{matrix}

<div id="blocks">
{blocks}
<div id="empty">No dedicated blocks for this pair yet — the coverage grid above shows
where the data currently sits. This is where new sources slot in.</div>
</div>

<div class="foot">
<b>Sources &amp; honesty.</b> Volumes and prices: HMRC Overseas Trade Statistics (fresh
blueberries, 08104050), reconciled across vintages. Chilean detail: Aduana DUS customs
records. Destination &amp; origin prices: UN Comtrade (HS 081040). China access: SAG
orchard roster. Each block is stamped with its source; the two-week edge is validated
out-of-sample on the Chilean lane only. The discipline is the product.
</div>
</div>

<script>
(function(){{
  var exp=document.getElementById('exp'), imp=document.getElementById('imp');
  function apply(){{
    var key=exp.value+'|'+imp.value, shown=0;
    document.querySelectorAll('.block').forEach(function(b){{
      var ok=b.getAttribute('data-pair')===key;
      b.style.display=ok?'':'none'; if(ok)shown++;
    }});
    document.getElementById('empty').style.display=shown?'none':'';
    document.getElementById('crumb').textContent=
      exp.value+' \\u2192 '+imp.value+'  ·  '+shown+(shown===1?' block':' blocks');
    document.querySelectorAll('#matrix td.cell').forEach(function(c){{
      c.classList.toggle('sel', c.getAttribute('data-pair')===key);
    }});
  }}
  window.pick=function(e,i){{ exp.value=e; imp.value=i; apply();
    document.getElementById('blocks').scrollIntoView({{behavior:'smooth',block:'start'}}); }};
  exp.addEventListener('change',apply); imp.addEventListener('change',apply);
  exp.value='{default_exp}'; imp.value='{default_imp}'; apply();
}})();
</script>
</body></html>"""


_ORIGIN_TPL = """
<h2>What every origin charges — and the freight wedge</h2>
<p class="deck">Two prices per supplier: what the fruit costs leaving its own country
(FOB) and what it's worth landed in Britain (CIF). The gap is mostly ocean freight.</p>
<p>Same fruit, two ends of the journey. The grey dot is each origin's own export price;
the purple dot is what Britain pays for it at the border ({year}). The distance between
them is the freight-and-insurance wedge — wide for the <em>deep-sea</em> origins (Chile
and South Africa carry roughly £0.7–1.7/kg of shipping), slim for near-Europe. Where the
wedge goes <em>negative</em> the country is a <em>re-export hub</em>, not a true grower —
the Netherlands' "exports" are largely fruit landed elsewhere first, so its FOB sits
above the UK border price. A clean tell for which origins actually grow what they ship.
(Lanes under ~250 t/yr are dropped — Comtrade revises their unit values too heavily.)</p>
<figure><img src="{chart}" alt="Origin export price vs UK landed price, by country">
<figcaption>Origin export FOB (UN Comtrade, reporter=origin, HS 081040) vs UK-landed CIF
(HMRC, value÷volume), {year}, USD→GBP at the live ECB rate. Annual; Comtrade
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
