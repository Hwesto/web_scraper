"""UK Blueberry Intelligence -- Streamlit dashboard.

Decision-first, confidence-everywhere. Reads only committed data (vintage store +
data/weekly CSVs) and the model functions, so it runs on Streamlit Community Cloud
straight off the public repo and refreshes whenever the Monday cron commits.

Run locally:   streamlit run dashboard/app.py
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import streamlit as st

from nowcast.call import weekly_call
from nowcast.config import REPO_ROOT
from nowcast.price import chile_fob_weekly
from nowcast.volume.uk_total import build_uk_total

st.set_page_config(page_title="UK Blueberry Intelligence", layout="wide",
                   initial_sidebar_state="expanded")

_REGION = {5: "Valparaíso", 6: "O'Higgins", 7: "Maule", 8: "Biobío", 9: "Araucanía",
           10: "Los Lagos", 13: "Metropolitana", 14: "Los Ríos", 16: "Ñuble"}


# ---------- cached data loaders (no network; committed data only) ----------
@st.cache_data(show_spinner="Fitting the whole-market supply model…")
def uk_total():
    return build_uk_total()


@st.cache_data
def call(d: _dt.date):
    return weekly_call(d)


@st.cache_data
def fob():
    return chile_fob_weekly()


@st.cache_data
def producers():
    p = REPO_ROOT / "data" / "weekly" / "chile_uk_blueberry_by_producer.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def _iso_to_date(w: str) -> pd.Timestamp:
    return pd.Timestamp.fromisocalendar(int(w[:4]), int(w.split("-W")[1]), 1)


def chip(label: str, kind: str):
    colour = {"ok": "#1a7f37", "warn": "#9a6700", "gap": "#cf222e", "ctx": "#57606a"}[kind]
    st.markdown(f"<span style='background:{colour};color:white;padding:2px 8px;"
                f"border-radius:10px;font-size:0.75rem'>{label}</span>", unsafe_allow_html=True)


# ============================ sidebar ============================
st.sidebar.title("🫐 UK Blueberry Intelligence")
st.sidebar.caption("Free, self-updating (GitHub Actions). Every number wears its confidence.")
as_of = st.sidebar.date_input("As-of date (replay any week)", value=_dt.date(2025, 1, 20),
                              min_value=_dt.date(2022, 6, 1), max_value=_dt.date.today())
st.sidebar.markdown("---")
st.sidebar.markdown("**Confidence legend**")
chip("● validated edge", "ok"); chip("◐ data-derived / partial", "warn")
chip("◯ context (weak)", "ctx"); chip("⚠ honest gap / paid", "gap")


# ============================ 1. THE CALL ============================
c = call(as_of)
st.subheader(f"This week's call — {c['origin']} arrivals, landing {c['landing_month']}")
if not c["in_season"]:
    st.info(f"**Off-season** — no {c['origin']} fruit shipping. The whole-market view below "
            f"stays live year-round; watch the in-season deep-sea lane.")
else:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Arrivals nowcast", f"{c['arrivals_nowcast_t']:,.0f} t",
              f"{c['anomaly_pct']:+.0f}% vs normal")
    k2.metric("Seasonal norm", f"{c['seasonal_norm_t']:,.0f} t")
    k3.metric("Supply signal", c["supply_signal"].split()[0])
    k4.metric("FOB cost (~2wk lead)", f"${c['fob_usd_kg']:.2f}/kg" if c["fob_usd_kg"] else "n/a",
              f"{c['fob_trend_pct']:+.0f}% m/m" if c["fob_trend_pct"] is not None else None,
              delta_color="inverse")
    st.success(f"**ACTION:** {c['action']}")
    a, b, d = st.columns(3)
    with a: chip("supply: validated nowcast · 66% backtest · ~2wk lead", "ok")
    with b: chip("FOB cost: declared, data-derived", "warn")
    with d: chip("UK sell-price direction: weak, NOT a forecast", "ctx")
st.markdown("---")


# ============================ 2. WHOLE-MARKET SUPPLY ============================
st.subheader("Whole-market UK supply — year-round, never blank")
ut = uk_total()
w = ut["weekly"].copy()
w["date"] = w["iso_week"].map(_iso_to_date)
origin_cols = [c2 for c2 in ut["origin_cols"] if c2 in w.columns]
area = w.set_index("date")[origin_cols].clip(lower=0) / 1000  # tonnes
area = area[area.index >= (area.index.max() - pd.Timedelta(weeks=104))]
st.area_chart(area, height=320)
left, right = st.columns([3, 2])
left.caption(f"Deep-sea lanes (can lead): {', '.join(ut['deep_sea'])}.  "
             f"Live weekly feed today: {', '.join(ut['live_lanes_available'])} "
             f"(others HMRC-benchmarked).")
with right:
    chip("reconciled to HMRC every month", "ok"); chip("live shipment shape on Chile", "ok")
st.markdown("---")


# ============================ 3. PRICE / COST ============================
cc1, cc2 = st.columns(2)
with cc1:
    st.subheader("Chilean FOB cost (8-yr history, ~2wk lead)")
    f = fob()
    if len(f):
        ff = f[f > 0].rename("FOB USD/kg")
        st.line_chart(ff[ff.index >= ff.index.max() - pd.Timedelta(weeks=160)], height=260)
        chip("declared export price, data-derived", "warn")
    else:
        st.write("FOB series not yet built.")
with cc2:
    st.subheader("UK sell-side price")
    st.warning("**Honest gap:** no free UK wholesale *spot* price during the Chile season "
               "(DEFRA blueberry is Jun–Nov only; NCGM is request-only). Sell-price *direction* "
               "does not back-test (≈coin-flip). Pair the leading FOB cost with your own demand view.")
    chip("retail = sticky context", "ctx"); chip("sell-spot in-season = paid line", "gap")
st.markdown("---")


# ============================ 4. WHO & WHAT IS LANDING ============================
st.subheader("Who & what is landing — named producers, cultivar, region")
p = producers()
if len(p):
    p = p.copy()
    p["region_name"] = p["top_region"].map(_REGION).fillna(p["top_region"].astype(str))
    top = p.sort_values("net_kg", ascending=False).head(15)
    cA, cB = st.columns([2, 3])
    with cA:
        st.bar_chart(top.set_index("producer")["net_kg"] / 1000, height=360, horizontal=True)
    with cB:
        st.dataframe(top[["producer", "net_kg", "top_cultivar", "region_name"]]
                     .rename(columns={"net_kg": "kg", "top_cultivar": "cultivar",
                                      "region_name": "region"}),
                     hide_index=True, width="stretch", height=360)
    g1, g2, g3, g4 = st.columns(4)
    with g1: chip("producer named: ~91% of kg", "warn")
    with g2: chip("region: ~100%", "ok")
    with g3: chip("cultivar: ~46% (source ceiling)", "warn")
    with g4: chip("cert: GLOBALG.A.P. (inferred, UK market)", "ctx")
else:
    st.write("Producer attribution not available.")
st.markdown("---")


# ============================ 5. CONFIDENCE LEDGER ============================
st.subheader("Confidence ledger — what's proven vs context vs honest gap")
L, M, R = st.columns(3)
with L:
    st.markdown("**● Validated edge**")
    st.markdown("- Within-month arrivals nowcast: **+12% OOS, 66% directional, ~2wk lead**\n"
                "- Weekly volume reconciled to HMRC (**0.1 kg**)\n"
                "- Chile origin↔HMRC cross-check **corr 0.92**")
with M:
    st.markdown("**◐ Data-derived / context**")
    st.markdown("- FOB cost (declared, 8-yr)\n- Named producers 91% · region 100% · cultivar 46%\n"
                "- Whole-market fused volume (all origins)")
with R:
    st.markdown("**⚠ Honest gaps / paid**")
    st.markdown("- UK sell-price direction: **doesn't back-test**\n"
                "- Peru weekly nowcast + names: **paid**\n"
                "- Named certified *orchard*: paid CIREN / your GGNs")
st.caption("5 clean negatives + 1 validated edge + 3 caught false-positives. "
           "The discipline is the product.")
