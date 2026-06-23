"""Render docs/data.html -- the Data Catalog: every dataset, browsable + downloadable.

The narrative dashboard (atlas.html) tells the story; the registry catalogues what *exists*;
this is the third view -- every committed dataset with a description, shape, columns, a live
preview, and a download link. It also copies the CSVs into docs/data/ so they're downloadable
on GitHub Pages (the data-export layer).

Run: python scripts/build_data_catalog.py
"""
from __future__ import annotations

import csv
import datetime as _dt
import html
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "atlas"
OUT = ROOT / "docs" / "data.html"
OUTDATA = ROOT / "docs" / "data"

# filename -> (category, title, blurb). Order of CATEGORIES sets section order.
CATEGORIES = ["Trade — global", "Trade — EU/US (fresher)", "Production", "Current season (committee snapshots)",
              "Analysis (derived)", "Condition", "Meta / reference", "Multi-fruit (generalisation proof)"]
META = {
    "comtrade_global_ranking.csv": ("Trade — global", "Global exporter/importer ranking",
        "UN Comtrade HS 081040, every reporter × role × year (2012→), value + $/kg + share + provisional flag."),
    "comtrade_bilateral.csv": ("Trade — global", "Bilateral lanes (both flows)",
        "Exporter→importer lanes, both exporter- and importer-reported, value + net_kg + $/kg. The mirror backbone."),
    "comtrade_monthly.csv": ("Trade — global", "Monthly seasonality",
        "Exporter→importer by month — the seasonal relay (who supplies the world when)."),
    "eurostat_monthly.csv": ("Trade — EU/US (fresher)", "EU monthly imports by origin (to 2026)",
        "Eurostat COMEXT, all 27 EU reporters aggregated, monthly to 2026-04. Beats Comtrade's lag; backtested."),
    "eurostat_blueberry.csv": ("Trade — EU/US (fresher)", "EU annual bilateral (9 reporters)",
        "Eurostat COMEXT annual, EUR/kg — the annual EU lane table."),
    "usda_movement.csv": ("Trade — EU/US (fresher)", "US supply by origin (USDA-AMS)",
        "US shipments by origin — domestic states + import arrivals (Peru/Chile/Mexico), season-to-date tonnes."),
    "faostat_blueberry.csv": ("Production", "FAOSTAT production / area / yield",
        "Every producing country's area_ha, production_t, yield (1961→). NOTE: no China (see production.csv)."),
    "production.csv": ("Production", "Production snapshots (FAOSTAT gaps)",
        "Patches FAOSTAT's holes: China 810kt (world #1), South Africa, Argentina, Serbia — and the corrected ranking."),
    "campaigns.csv": ("Current season (committee snapshots)", "Current-season committee totals",
        "Peru/Chile/Spain/Morocco/Mexico/Argentina season export totals + growth — the real-time exporter layer."),
    "sa_exports.csv": ("Current season (committee snapshots)", "South Africa weekly (Berries ZA, auto-parsed)",
        "Berries ZA weekly export PDF, parsed to year-to-date by destination region."),
    "china.csv": ("Current season (committee snapshots)", "China dossier (production + imports + price)",
        "The gated bloc as a snapshot: domestic production 810kt, imports by origin, the -50% price collapse."),
    "peru_exporters.csv": ("Current season (committee snapshots)", "Peru named exporters",
        "Top-15 Peruvian exporters by volume + FOB + YoY (Camposol, Hortifrut…) — depth Comtrade can't give."),
    "mx_registered_orchards.csv": ("Current season (committee snapshots)", "Mexico China-export orchards",
        "SENASICA roster of named Mexican orchards authorised for China — entity-level depth."),
    "usda_forecasts.csv": ("Current season (committee snapshots)", "USDA-FAS GAIN forecasts",
        "Season-ahead production/export forecasts (Peru, Mexico) — the forward axis."),
    "global_reconcile.csv": ("Analysis (derived)", "Global trade reconciliation",
        "Per origin × year: exports vs world-imports (mirror), and EU/US/Asia/UK accounted share + residual."),
    "eurostat_backtest.csv": ("Analysis (derived)", "Eurostat-vs-Comtrade backtest",
        "Validates the monthly EU pipeline against Comtrade for prior years (median |diff| 9.4%)."),
    "divergence.csv": ("Analysis (derived)", "Forecast-vs-actual divergence",
        "Where reality broke from the projections — flagged BEAT/MISS/REVERSAL/SURPRISE."),
    "weather_regions.csv": ("Condition", "Growing-region weather (NASA POWER)",
        "Monthly temp/frost/rain for 14 growing regions (incl. Yunnan, La Libertad…) — the frost lens."),
    "registry.csv": ("Meta / reference", "The atlas — coverage registry",
        "179 rows: what data exists per commodity×country×data-point, flagged free/paid/none + wired. The moat."),
    "hs_codes.csv": ("Meta / reference", "HS/commodity codes",
        "HS6 + national codes per commodity — the join keys (HS code is a parameter)."),
    "country_codes.csv": ("Meta / reference", "Country codes (M49/ISO)",
        "M49 ↔ ISO2/ISO3 ↔ name — the cross-source bridge."),
    "probe_log.csv": ("Meta / reference", "Source reachability probe",
        "Weekly clean-egress probe of overlay sources (status, access hint)."),
    "comtrade_global_ranking_avocado.csv": ("Multi-fruit (generalisation proof)", "Avocado ranking",
        "Proof the machine generalises: the same Comtrade sweep run with commodity=avocado."),
    "faostat_avocado.csv": ("Multi-fruit (generalisation proof)", "Avocado production",
        "FAOSTAT avocado — Mexico #1, the same production layer with the HS/item swapped."),
}


def _preview(path: Path, n: int = 8) -> str:
    with open(path, encoding="utf-8") as f:
        rd = csv.reader(f)
        rows = list(rd)
    if not rows:
        return ""
    hdr, body = rows[0], rows[1:n + 1]
    th = "".join(f"<th>{html.escape(c)}</th>" for c in hdr)
    trs = []
    for r in body:
        tds = "".join(f"<td>{html.escape(c[:24])}</td>" for c in r)
        trs.append(f"<tr>{tds}</tr>")
    return f'<table class="prev"><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def build() -> Path:
    OUTDATA.mkdir(parents=True, exist_ok=True)
    cards: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for path in sorted(SRC.glob("*.csv")):
        name = path.name
        shutil.copy(path, OUTDATA / name)                 # serve raw on Pages
        cat, title, blurb = META.get(name, ("Meta / reference", name, ""))
        with open(path, encoding="utf-8") as f:
            rd = csv.reader(f); hdr = next(rd, []); nrows = sum(1 for _ in rd)
        cols = ", ".join(hdr)
        cards.setdefault(cat, []).append(
            f'<div class="ds"><h3>{html.escape(title)} '
            f'<a class="dl" href="data/{name}" download>⬇ {name}</a></h3>'
            f'<p class="blurb">{html.escape(blurb)}</p>'
            f'<p class="shape"><b>{nrows:,}</b> rows × {len(hdr)} cols · <code>{html.escape(cols)}</code></p>'
            f'{_preview(path)}</div>')
    sections = []
    for cat in CATEGORIES:
        if cards.get(cat):
            sections.append(f'<h2>{html.escape(cat)}</h2>' + "".join(cards[cat]))
    OUT.write_text(_PAGE.format(today=_dt.date.today().isoformat(),
                                n=len(list(SRC.glob("*.csv"))), body="".join(sections)), encoding="utf-8")
    return OUT


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>The Global Blueberry Atlas — Data Catalog</title>
<style>
:root{{--paper:#faf8f4;--ink:#1d1c1a;--subtle:#6c655c;--accent:#2f6f4e;--line:#e6e2db}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);
 font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.5}}
header,main{{max-width:1100px;margin:0 auto;padding:0 22px}}
header{{padding-top:32px}} h1{{font-family:Georgia,serif;font-size:2.2rem;margin:0 0 4px}}
.sub{{color:var(--subtle);margin:0 0 6px}} nav a{{color:var(--accent);font-weight:600;text-decoration:none;margin-right:16px}}
h2{{font-family:Georgia,serif;font-size:1.4rem;margin:30px 0 6px;border-top:2px solid var(--ink);padding-top:10px}}
.ds{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 16px;margin:12px 0}}
.ds h3{{font-size:1.05rem;margin:0 0 3px;display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
.dl{{font-size:.8rem;font-weight:600;color:var(--accent);text-decoration:none;white-space:nowrap}}
.blurb{{color:var(--ink);margin:0 0 5px;font-size:.92rem}}
.shape{{color:var(--subtle);font-size:.8rem;margin:0 0 8px}} .shape code{{font-size:.76rem}}
.prev{{border-collapse:collapse;font-size:.78rem;width:100%;display:block;overflow-x:auto;white-space:nowrap}}
.prev th{{text-align:left;color:var(--subtle);border-bottom:1px solid var(--ink);padding:3px 8px;font-weight:600}}
.prev td{{padding:3px 8px;border-bottom:1px solid var(--line);color:#333}}
footer{{max-width:1100px;margin:0 auto;padding:24px 22px 50px;color:var(--subtle);font-size:.82rem;border-top:1px solid var(--line)}}
</style></head><body>
<header>
<h1>Data Catalog</h1>
<p class="sub">Every committed dataset in the Global Blueberry Atlas — {n} tables, browsable and downloadable.</p>
<nav><a href="./atlas.html">← The atlas (narrative)</a><a href="./atlas.html#atlas">The coverage map</a></nav>
</header>
<main>{body}</main>
<footer>Built {today}. Each table is committed CSV under <code>data/atlas/</code>, mirrored to
<code>docs/data/</code> for download. Free, public sources — every figure traceable to its row.</footer>
</body></html>"""


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size/1024:.0f} KB) + mirrored CSVs to docs/data/")
