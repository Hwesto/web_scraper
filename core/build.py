"""Assemble the lean UK blueberry market report (Markdown) from the two views."""
from __future__ import annotations

import datetime as _dt

from nowcast.config import REPO_ROOT
from core import player_exports, uk_market

OUT = REPO_ROOT / "core" / "uk_market_report.md"


def _md(df, cols=None) -> str:
    df = df[cols] if cols else df
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join(["---"] * len(df.columns)) + "|"
    rows = ["| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def build() -> str:
    v1 = uk_market.into_uk()
    s = uk_market.uk_supply()
    L = [f"# Britain's blueberry market — core",
         f"_generated {_dt.date.today().isoformat()} · free data (HMRC · UN Comtrade · DEFRA)_", "",
         f"UK imports **~{s['imports_kt']:.0f} kt/yr**, grows **{s['uk_production_kt']:.1f} kt** "
         f"itself → **{s['self_sufficiency_pct']}% self-sufficient**.", "",
         "## View 1 — into the UK (who, when, landed price, variety)",
         "_share of last-12-month imports; CIF £/kg = price brought in (declared landed "
         "value, often consignment-settled); variety from Chile DUS only._", "",
         _md(v1), "",
         "## View 2 — where each major player else ships (2024, % of their tonnage)",
         "_UN Comtrade, annual — the resolution complete for all players (monthly is patchy)._", ""]
    for p in player_exports.PLAYERS.values():
        d = player_exports.by_player(p).head(6).copy()
        if d.empty:
            continue
        d["$/kg"] = d["cif_usd_kg"].round(2); d["%t"] = d["pct_tonnage"]
        L += [f"### {p}", _md(d, ["destination", "%t", "$/kg"]), ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    return OUT.read_text()


if __name__ == "__main__":
    build()
    print(f"wrote {OUT}")
