"""The global bilateral flow + price grid for blueberries (HS 081040).

The Comtrade sweep (`comtrade_sweep`) ranks each country's *total* trade; this
fills the cells *between* them -- for every major exporter, its exports to every
partner, with the realised unit value (value/weight = the price that lane fetched).
It generalises the per-origin destination tables that existed only for Chile and
Peru (`market/comtrade.py`) to the whole exporter target set, so the registry's
"bilateral flow + price matrix" row is real globally, not just two lanes.

One preview call per exporter (reporterCode=code, all partners, partner2Code=0 --
the same aggregate-row pin the sweep uses), committed to
`data/atlas/comtrade_bilateral.csv`. No key. Annual; the latest ~2 years are
provisional (staggered reporting -- see `comtrade_sweep`).
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR, countries, comtrade_sweep, hs_codes
from atlas.comtrade_sweep import START_YEAR

CACHE = ATLAS_DIR / "comtrade_bilateral.csv"
_URL = ("https://comtradeapi.un.org/public/v1/preview/C/A/HS"
        "?reporterCode={rep}&period={yr}&cmdCode={hs}&flowCode={flow}"
        "&partnerCode=&partner2Code=0&motCode=0&customsCode=C00")
_COLS = ["year", "exporter_code", "exporter", "importer_code", "importer",
         "flow", "value_usd", "net_kg", "unit_usd_kg", "provisional"]
_MIN_KG = 1_000          # drop trace lanes (tiny-N unit values lie -- HANDOFF gotcha)


def _num(row: dict, key: str) -> float:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _fetch(reporter: int, year: int, hs: str, flow: str, retries: int = 4) -> list[dict]:
    url = _URL.format(rep=reporter, yr=year, hs=hs, flow=flow)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("data", []) or []
        except Exception as e:                         # noqa: BLE001 -- retry any net error
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Comtrade matrix fetch failed (reporter={reporter} {year}): {last}")


def _exporter_codes(year: int | None) -> list[int]:
    """The exporter target set (95% of trade) from the sweep, if available."""
    ts = comtrade_sweep.target_set("exporter", year=year, include_provisional=year is not None)
    if not ts.empty:
        return [int(c) for c in ts["reporter_code"]]
    return [604, 528, 724, 152, 504, 842, 484, 124, 616, 710]   # fallback top exporters


def _importer_codes(year: int | None) -> list[int]:
    """The importer target set (95% of trade) from the sweep, if available."""
    ts = comtrade_sweep.target_set("importer", year=year, include_provisional=year is not None)
    if not ts.empty:
        return [int(c) for c in ts["reporter_code"]]
    return [842, 528, 276, 826, 124, 156, 724, 616]   # fallback top importers


def _lane(r: dict, rep: int, flow: str, year: int, prov: bool, names: dict) -> dict | None:
    """One Comtrade row -> a lane oriented exporter->importer regardless of which side
    reported it (flow=X: reporter exports; flow=M: reporter imports)."""
    pc = int(_num(r, "partnerCode"))
    if pc == 0:                                        # World aggregate
        return None
    val, wgt = _num(r, "primaryValue"), _num(r, "netWgt")
    if val <= 0 or wgt < _MIN_KG:
        return None
    exp_c, imp_c, reported = (rep, pc, "exporter") if flow == "X" else (pc, rep, "importer")
    return {"year": year, "exporter_code": exp_c, "exporter": names.get(exp_c, f"M49-{exp_c}"),
            "importer_code": imp_c, "importer": names.get(imp_c, f"M49-{imp_c}"),
            "flow": reported, "value_usd": val, "net_kg": wgt,
            "unit_usd_kg": round(val / wgt, 4), "provisional": prov}


def refresh(years: list[int], exporters: list[int] | None = None,
            importers: list[int] | None = None,
            names: dict[int, str] | None = None) -> pd.DataFrame:
    """Bidirectional bilateral grid: exporter-reported exports (flow=X) for the exporter
    target set + importer-reported imports (flow=M) for the importer target set, both
    oriented exporter->importer with a `flow` tag for the reporting side (so `mirror_check`
    can reconcile the two). (Re)writes the cache."""
    hs = hs_codes.hs6("blueberry")
    names = names or countries.name_map()
    parts = []
    for year in years:
        prov = comtrade_sweep.is_provisional(year)
        exp = exporters if exporters is not None else _exporter_codes(None)
        imp = importers if importers is not None else _importer_codes(None)
        for rep, flow in [(c, "X") for c in exp] + [(c, "M") for c in imp]:
            rows = [d for r in _fetch(rep, year, hs, flow)
                    if (d := _lane(r, rep, flow, year, prov, names)) is not None]
            parts.append(pd.DataFrame(rows, columns=_COLS).drop_duplicates(
                subset=["year", "exporter_code", "importer_code", "flow"]))
            time.sleep(0.4)
    fresh = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=_COLS)
    if CACHE.exists() and not fresh.empty:
        old = pd.read_csv(CACHE)
        if "flow" not in old.columns:                  # migrate a pre-both-flows cache
            old["flow"] = "exporter"
        old = old[~old["year"].isin(years)]
        fresh = pd.concat([old, fresh], ignore_index=True)
    fresh = fresh.sort_values(["year", "value_usd"], ascending=[True, False]).reset_index(drop=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(CACHE, index=False)
    return fresh


def load() -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    return pd.read_csv(CACHE)


def lanes(exporter: str | None = None, importer: str | None = None,
          year: int | None = None, flow: str | None = "exporter") -> pd.DataFrame:
    """Filter the grid to an exporter and/or importer (latest year if None). Defaults to
    the exporter-reported view (`flow='exporter'`) so a lane isn't double-counted; pass
    flow=None for both reporting sides."""
    df = load()
    if df.empty:
        return df
    year = year or int(df["year"].max())
    df = df[df["year"] == year]
    if flow is not None and "flow" in df.columns:
        df = df[df["flow"] == flow]
    if exporter is not None:
        df = df[df["exporter"] == exporter]
    if importer is not None:
        df = df[df["importer"] == importer]
    return df.sort_values("value_usd", ascending=False).reset_index(drop=True)


def mirror_check(year: int | None = None, min_value: float = 1_000_000) -> pd.DataFrame:
    """Reconcile exporter-reported vs importer-reported value for the same lane.
    ratio = exporter-reported / importer-reported; ~1 means the two sides agree (the
    classic Comtrade mirror gap). Only lanes material on at least one side."""
    df = load()
    if df.empty or "flow" not in df.columns:
        return pd.DataFrame()
    year = year or int(df["year"].max())
    d = df[df["year"] == year]
    x = (d[d["flow"] == "exporter"][["exporter", "importer", "value_usd"]]
         .rename(columns={"value_usd": "exp_reported"}))
    m = (d[d["flow"] == "importer"][["exporter", "importer", "value_usd"]]
         .rename(columns={"value_usd": "imp_reported"}))
    j = x.merge(m, on=["exporter", "importer"], how="inner")
    j = j[(j["exp_reported"] >= min_value) | (j["imp_reported"] >= min_value)]
    j["ratio"] = (j["exp_reported"] / j["imp_reported"]).round(2)
    return j.sort_values("exp_reported", ascending=False).reset_index(drop=True)


if __name__ == "__main__":                             # python -m atlas.comtrade_matrix
    this = _dt.date.today().year
    df = refresh(list(range(START_YEAR, this + 1)))    # full history 2012->present
    print(f"cached {len(df)} bilateral lanes ({START_YEAR}->{this}) -> {CACHE}")
    if len(df):
        yr = int(df[~df["provisional"]]["year"].max()) if (~df["provisional"]).any() \
            else int(df["year"].max())
        top = lanes(year=yr).head(10)
        print(f"\ntop blueberry lanes {yr} (USD/kg):")
        print(top[["exporter", "importer", "value_usd", "net_kg", "unit_usd_kg"]]
              .to_string(index=False))
