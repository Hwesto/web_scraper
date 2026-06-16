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

# --- POSITIONAL layout, pinned from the inspect run log (84 ;-sep cols, no header) ---
# Anchored by col 20 = GLOSAPAISDESTINO ("PERU" in the sample) matching the metadata
# dictionary, so header fields are 1:1 with columns 0..60, items follow.
IDX = {0: "fecha", 14: "region", 19: "pais_code", 20: "pais",
       69: "arancel", 70: "unidad", 71: "cantidad"}
FRESH_PREFIX = "08104"         # fresh blueberry (Vaccinium); frozen 0811 excluded
UK_GLOSA = "REINO UNIDO"       # GLOSAPAISDESTINO value for the UK
SEP = ";"
ENC = "latin-1"


def _read_cols(flat: Path) -> pd.DataFrame:
    df = pd.read_csv(flat, sep=SEP, header=None, usecols=list(IDX), dtype=str,
                     encoding=ENC, on_bad_lines="skip")
    return df.rename(columns=IDX)


def _blueberry_uk(df: pd.DataFrame) -> pd.DataFrame:
    m = (df["arancel"].astype(str).str.strip().str.startswith(FRESH_PREFIX)
         & df["pais"].astype(str).str.strip().str.upper().eq(UK_GLOSA))
    return df[m].copy()


def _ckan(action: str, **params) -> dict:
    r = requests.get(f"{CKAN}/{action}", params=params, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.json()["result"]


def _resources(year: int) -> list[dict]:
    # Dataset slugs are INCONSISTENT across years: 2024-25 use
    # "registro-de-exportaciones-{y}" (plural), 2018-23 + 2026 use
    # "registro-de-exportacion-{y}" (singular), older years "registros-...".
    # Try the variants; tolerate 404 so collect() skips genuinely missing years.
    for slug in (f"registro-de-exportaciones-{year}",
                 f"registro-de-exportacion-{year}",
                 f"registros-de-exportacion-{year}"):
        try:
            return _ckan("package_show", id=slug)["resources"]
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                continue
            raise
    print(f"no dataset for {year} (tried slug variants) -- skipping")
    return []


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


def _month_rar(resources: list[dict], month_token: str) -> dict | None:
    for r in resources:
        name = (r.get("name") or "").lower()
        if (r.get("format") or "").lower() == "rar" and month_token in name \
                and "bulto" not in name and "transporte" not in name:
            return r
    return None


def _iter_month_rars(resources: list[dict]):
    for r in resources:
        name = (r.get("name") or "").lower()
        if (r.get("format") or "").lower() != "rar" or "exportaciones" not in name:
            continue
        if "bulto" in name or "transporte" in name:
            continue
        yield r


def inspect(year: int, month_token: str) -> None:
    res = _resources(year)
    print("RESOURCES:", [(r["name"], r["format"]) for r in res][:8])
    rar = _month_rar(res, month_token)
    print("MONTH RAR:", rar and rar["name"], rar and rar["url"])
    if not rar:
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        df = _read_cols(_extract_flatfile(_download(rar["url"], td / "m.rar"), td))
    print("rows:", len(df), "| sample destinations:",
          df["pais"].astype(str).str.strip().str.upper().value_counts().head(8).to_dict())
    fresh = df[df["arancel"].astype(str).str.strip().str.startswith(FRESH_PREFIX)]
    print("FRESH-BLUEBERRY rows (08104*):", len(fresh))
    print("  blueberry destinations:",
          fresh["pais"].astype(str).str.strip().str.upper().value_counts().head(10).to_dict())
    print("  arancel codes:", fresh["arancel"].str.strip().value_counts().head().to_dict())
    bb = _blueberry_uk(df)
    print(f"BLUEBERRY -> {UK_GLOSA}: {len(bb)} rows")
    if len(bb):
        print(bb[["fecha", "region", "arancel", "unidad", "cantidad"]].head(8).to_string())


def collect(years: list[int]) -> None:
    weekly: dict[str, float] = {}
    for y in years:
        for r in _iter_month_rars(_resources(y)):
            with tempfile.TemporaryDirectory() as td:
                td = Path(td)
                try:
                    df = _read_cols(_extract_flatfile(_download(r["url"], td / "m.rar"), td))
                except Exception as exc:
                    print(f"skip {r['name']}: {exc}")
                    continue
            bb = _blueberry_uk(df)
            if bb.empty:
                print(f"{r['name']}: 0 blueberry-UK rows")
                continue
            bb["d"] = pd.to_datetime(bb["fecha"], format="%d%m%Y", errors="coerce")
            bb["qty"] = pd.to_numeric(bb["cantidad"].str.replace(",", "."), errors="coerce")
            bb = bb.dropna(subset=["d", "qty"])
            for ts, qty in bb.groupby(bb["d"].dt.strftime("%G-W%V"))["qty"].sum().items():
                weekly[ts] = weekly.get(ts, 0.0) + float(qty)
            print(f"{r['name']}: +{len(bb)} blueberry-UK rows, {bb['qty'].sum():.0f} kg")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(sorted(weekly.items()), columns=["iso_week", "net_kg"])
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(out)} weeks, {out['net_kg'].sum():.0f} kg total")


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
