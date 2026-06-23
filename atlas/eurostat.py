"""EU blueberry trade from Eurostat COMEXT (HS 081040) -- one free, no-key source
that backs every catalogued EU lane at once.

COMEXT dataset DS-045409 ("EU trade since 1988 by HS2-4-6") serves blueberry
trade (HS6 = 081040, matching the Comtrade base layer) for every EU member as
reporter, by partner, flow and year -- via the dissemination SDMX/JSON-stat API
with no key (verified reachable + parseable 2026-06). This wires the nine EU
rows the registry had as `free/unwired` (ES, NL, PL, DE, FR, PT, BE, IT, AT)
into one committed table.

Dimensions (order): freq . reporter . partner . product . flow . indicators . time.
Flow 1 = imports, 2 = exports. Indicators kept: VALUE_IN_EUROS and
QUANTITY_IN_100KG (-> kg = x100 -> realised EUR/kg unit value). Annual.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR, hs_codes

CACHE = ATLAS_DIR / "eurostat_blueberry.csv"
_API = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
# the EU members the atlas catalogues as blueberry exporters/importers
EU_REPORTERS = ["ES", "NL", "PL", "DE", "FR", "PT", "BE", "IT", "AT"]
_FLOW = {"1": "import", "2": "export"}
_COLS = ["year", "reporter", "partner", "flow", "value_eur", "net_kg", "eur_per_kg"]


def _fetch_jsonstat(reporters: list[str], year: int, retries: int = 4) -> dict:
    """One JSON-stat pull: given reporters, all partners, both flows, HS081040, a year."""
    hs = hs_codes.hs6("blueberry")
    rep = "+".join(reporters)
    # key: freq.reporter.partner.product.flow.indicators (partner & indicators empty = all)
    key = f"A.{rep}..{hs}.."
    url = (f"{_API}/{key}?format=JSON&startPeriod={year}&endPeriod={year}"
           "&i=VALUE_IN_EUROS&i=QUANTITY_IN_100KG")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:                         # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Eurostat COMEXT fetch failed ({rep} {year}): {last}")


def _decode(js: dict) -> list[dict]:
    """JSON-stat -> flat records keyed by dimension codes (sparse value dict)."""
    dims = js["id"]                                    # dimension order
    sizes = js["size"]
    cats = {d: js["dimension"][d]["category"]["index"] for d in dims}
    # position -> code per dimension (invert the index map)
    codes = {d: {p: c for c, p in cats[d].items()} for d in dims}
    strides = [1] * len(sizes)                         # row-major strides
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    out = []
    for flat, val in js["value"].items():
        idx = int(flat)
        rec = {}
        for i, d in enumerate(dims):
            rec[d] = codes[d][(idx // strides[i]) % sizes[i]]
        rec["_val"] = val
        out.append(rec)
    return out


def _is_country(partner: str) -> bool:
    """Keep real country partners + the WORLD total; drop Eurostat geo-aggregates
    (INT_EU/EXT_EA/EU27_2020/EA21/...) that would double-count the lanes."""
    return partner == "WORLD" or (len(partner) == 2 and partner.isalpha())


def _tidy(records: list[dict]) -> pd.DataFrame:
    """Pivot VALUE_IN_EUROS + QUANTITY_IN_100KG onto one row per lane; add EUR/kg."""
    rows: dict[tuple, dict] = {}
    for r in records:
        if not _is_country(r["partner"]):
            continue
        key = (int(r["time"]), r["reporter"], r["partner"], _FLOW.get(r["flow"], r["flow"]))
        cell = rows.setdefault(key, {"value_eur": 0.0, "net_kg": 0.0})
        if r["indicators"] == "VALUE_IN_EUROS":
            cell["value_eur"] = float(r["_val"])
        elif r["indicators"] == "QUANTITY_IN_100KG":
            cell["net_kg"] = float(r["_val"]) * 100.0   # 100kg -> kg
    out = []
    for (year, rep, partner, flow), cell in rows.items():
        if cell["value_eur"] <= 0:
            continue
        kg = cell["net_kg"]
        out.append({"year": year, "reporter": rep, "partner": partner, "flow": flow,
                    "value_eur": round(cell["value_eur"], 2), "net_kg": round(kg, 1),
                    "eur_per_kg": round(cell["value_eur"] / kg, 4) if kg > 0 else 0.0})
    return pd.DataFrame(out, columns=_COLS)


def refresh(years: list[int], reporters: list[str] | None = None) -> pd.DataFrame:
    """Fetch EU blueberry trade for the given years; (re)write the cache."""
    reporters = reporters or EU_REPORTERS
    parts = []
    for year in years:
        parts.append(_tidy(_decode(_fetch_jsonstat(reporters, year))))
        time.sleep(0.5)
    fresh = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=_COLS)
    if CACHE.exists() and not fresh.empty:
        old = pd.read_csv(CACHE)
        old = old[~old["year"].isin(years)]
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "reporter", "flow", "value_eur"],
                              ascending=[True, True, True, False]).reset_index(drop=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


if __name__ == "__main__":                             # python -m atlas.eurostat
    this = _dt.date.today().year
    df = refresh([this - 3, this - 2])                 # latest reasonably-complete years
    print(f"cached {len(df)} EU lane-rows -> {CACHE}")
    if len(df):
        yr = int(df["year"].max())
        x = df[(df["year"] == yr) & (df["flow"] == "export")]
        print(f"\ntop EU blueberry export lanes {yr} (EUR/kg):")
        print(x.head(8)[["reporter", "partner", "value_eur", "net_kg", "eur_per_kg"]]
              .to_string(index=False))
