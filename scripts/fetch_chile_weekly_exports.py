"""Fetch WEEKLY Chile->UK fresh-blueberry exports from the Aduana DUS records.

Runs on GitHub Actions (clean egress) because datos.gob.cl is TLS-blocked from
the Claude Code sandbox proxy. The export data are monthly .rar archives of
transaction-level DUS records (day-level FECHAACEPT), so they aggregate to ISO
weeks -- the resolution at which the 3-5 week deep-sea transit becomes a usable
lead over HMRC import (the monthly ODEPA series could not, see backtest/lead.py).

Two modes (this script CANNOT be tested from the sandbox; first run validates):
  --mode inspect : download the metadata + one month, LOG the column layout, the
                   distinct destinations for blueberry rows, and a sample. Run
                   this first (workflow_dispatch) and read the Action log to pin
                   the column names and the UK country code/label below.
  --mode collect : filter fresh blueberry (arancel 08104*) -> UK, aggregate
                   cantidad (net kg) by ISO week, write the weekly CSV.

Pin these two from the inspect log before trusting collect output:
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import requests

CKAN = "https://datos.gob.cl/api/3/action"
HEADERS = {"User-Agent": "Mozilla/5.0 (uk-blueberry-nowcast weekly-collector)"}
OUT = Path("data/weekly/chile_uk_blueberry_weekly.csv")

# --- pin from the inspect-mode log ---
COL_DATE = "FECHAACEPT"        # day-level DUS acceptance date
COL_TARIFF = "CODIGOARANCEL"   # tariff/arancel code column
COL_DEST = "PAIS_DESTINO"      # destination country code or name column
COL_QTY = "CANTIDADMERCANCIA"  # net quantity (kg)
FRESH_PREFIX = "08104"         # fresh blueberry (Vaccinium); frozen 0811 excluded
UK_VALUES = {"224", "Reino Unido", "REINO UNIDO", "GBR", "GB"}  # widen after inspect
SEP = ";"


def _ckan(action: str, **params) -> dict:
    r = requests.get(f"{CKAN}/{action}", params=params, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.json()["result"]


def _resources(year: int) -> list[dict]:
    # Annual packages lag (e.g. the current year may not exist yet) -> tolerate 404
    # so collect() skips missing years instead of crashing.
    try:
        return _ckan("package_show", id=f"registro-de-exportaciones-{year}")["resources"]
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            print(f"no dataset for {year} (404) -- skipping")
            return []
        raise


def _download(url: str, dest: Path) -> Path:
    with requests.get(url, headers=HEADERS, timeout=600, stream=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return dest


def _extract_flatfile(rar: Path, workdir: Path) -> Path:
    # GitHub runner: `sudo apt-get install -y unar` (handles .rar, free).
    subprocess.run(["unar", "-quiet", "-output-directory", str(workdir), str(rar)],
                   check=True)
    candidates = [p for p in workdir.rglob("*") if p.is_file() and p.suffix.lower()
                  in (".csv", ".txt", "")]
    if not candidates:
        raise RuntimeError(f"no flat file extracted from {rar.name}")
    return max(candidates, key=lambda p: p.stat().st_size)


def _read_metadata_columns(resources: list[dict]) -> list[str] | None:
    meta = next((r for r in resources if "metadata" in (r.get("name") or "").lower()
                 and (r.get("format") or "").lower() in ("xlsx", "xls")), None)
    if not meta:
        return None
    raw = requests.get(meta["url"], headers=HEADERS, timeout=120).content
    df = pd.read_excel(io.BytesIO(raw))
    # The metadata sheet lists field names (and order/description). Return its
    # first text column's values as the candidate column order.
    return [str(v) for v in df.iloc[:, 0].dropna().tolist()]


def _month_rar(resources: list[dict], month_token: str) -> dict | None:
    for r in resources:
        name = (r.get("name") or "").lower()
        if (r.get("format") or "").lower() == "rar" and month_token in name \
                and "bulto" not in name and "transporte" not in name:
            return r
    return None


def inspect(year: int, month_token: str) -> None:
    res = _resources(year)
    print("RESOURCES:", [(r["name"], r["format"]) for r in res][:8])
    cols = _read_metadata_columns(res)
    print("METADATA COLUMN CANDIDATES:", cols)
    rar = _month_rar(res, month_token)
    print("MONTH RAR:", rar and rar["name"], rar and rar["url"])
    if not rar:
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        flat = _extract_flatfile(_download(rar["url"], td / "m.rar"), td)
        head = pd.read_csv(flat, sep=SEP, nrows=5, header=None, dtype=str,
                           encoding="latin-1")
        print("FIRST ROWS (positional):")
        print(head.to_string())
        # If column names known, show blueberry destinations:
        try:
            df = pd.read_csv(flat, sep=SEP, header=None, names=cols, dtype=str,
                             encoding="latin-1") if cols else None
            if df is not None and COL_TARIFF in df.columns:
                bb = df[df[COL_TARIFF].astype(str).str.startswith(FRESH_PREFIX)]
                print("BLUEBERRY ROWS:", len(bb))
                if COL_DEST in bb.columns:
                    print("DISTINCT DESTINATIONS (blueberry):",
                          bb[COL_DEST].value_counts().head(20).to_dict())
        except Exception as exc:
            print("named-read failed (pin columns from positional rows):", exc)


def collect(years: list[int]) -> None:
    res_cache = {y: _resources(y) for y in years}
    weekly: dict[str, float] = {}
    for y in years:
        cols = _read_metadata_columns(res_cache[y])
        for r in res_cache[y]:
            name = (r.get("name") or "").lower()
            if (r.get("format") or "").lower() != "rar" or "exportaciones" not in name:
                continue
            if "bulto" in name or "transporte" in name:
                continue
            with tempfile.TemporaryDirectory() as td:
                td = Path(td)
                try:
                    flat = _extract_flatfile(_download(r["url"], td / "m.rar"), td)
                    df = pd.read_csv(flat, sep=SEP, header=None, names=cols,
                                     dtype=str, encoding="latin-1")
                except Exception as exc:
                    print(f"skip {r['name']}: {exc}")
                    continue
            bb = df[df[COL_TARIFF].astype(str).str.startswith(FRESH_PREFIX)
                    & df[COL_DEST].astype(str).isin(UK_VALUES)].copy()
            if bb.empty:
                continue
            bb["d"] = pd.to_datetime(bb[COL_DATE], errors="coerce", dayfirst=True)
            bb["qty"] = pd.to_numeric(bb[COL_QTY].str.replace(",", "."), errors="coerce")
            bb = bb.dropna(subset=["d", "qty"])
            for ts, qty in bb.groupby(bb["d"].dt.strftime("%G-W%V"))["qty"].sum().items():
                weekly[ts] = weekly.get(ts, 0.0) + float(qty)
            print(f"{r['name']}: +{len(bb)} blueberry-UK rows")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(sorted(weekly.items()), columns=["iso_week", "net_kg"])
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(out)} weeks")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["inspect", "collect"], default="inspect")
    ap.add_argument("--years", default="2024")
    ap.add_argument("--month-token", default="enero")
    args = ap.parse_args()
    years = [int(y) for y in str(args.years).split(",")]
    if args.mode == "inspect":
        inspect(years[0], args.month_token)
    else:
        collect(years)


if __name__ == "__main__":
    sys.exit(main())
