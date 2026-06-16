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
IDX = {0: "fecha", 4: "exp_rut", 5: "exp_num", 7: "exp_comuna",
       14: "region", 19: "pais_code", 20: "pais",
       62: "item_name", 63: "attr1", 64: "attr2",
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
    # datos.gob.cl returns transient 5xx; retry with backoff (404 raises through).
    delay = 5
    for attempt in range(5):
        r = requests.get(f"{CKAN}/{action}", params=params, headers=HEADERS, timeout=120)
        if r.status_code < 500:
            r.raise_for_status()
            return r.json()["result"]
        if attempt == 4:
            r.raise_for_status()
        import time as _t
        _t.sleep(delay)
        delay *= 2
    return {}


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
    import time as _t
    delay = 5
    for attempt in range(5):
        try:
            with requests.get(url, headers=HEADERS, timeout=600, stream=True) as r:
                if r.status_code >= 500:
                    raise requests.HTTPError(f"{r.status_code}", response=r)
                r.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                return dest
        except requests.RequestException:
            if attempt == 4:
                raise
            _t.sleep(delay)
            delay *= 2
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


# Known highbush cultivars that appear in the cargo description (attr2/item_name).
_CULTIVARS = ["BLUE RIBBON", "TOP SHELF", "LAST CALL", "SUZIBLUE", "SNOWCHASER",
              "LEGACY", "DUKE", "DRAPER", "VENTURA", "STELLA", "EUREKA", "CARGO",
              "CRUNCH", "ROCIO", "MAGNOLIA", "BIANCA", "KIRRA", "CAMELLIA",
              "BRIGITTA", "O'NEAL", "ONEAL", "ELLIOT", "STAR", "EMERALD", "JEWEL"]
_NOISE = ("CAJA", "NO ESPECIFICAD", "SIN-CODIGO", "SIN CODIGO", "BULK", "KN", "KG",
          "ARANDANO", "FRESCO", "AZUL", "CONVENCIONAL", "ORGANIC", "TRADICIONAL",
          "DIFERENTES", "VARIED")


def _clean_producer(attr1: str, item_name: str) -> str:
    """Extract the producer/marca. attr1 is usually 'NAME-F'; fall back to a
    '...-F' segment in item_name. Returns '' if only generic/noise text."""
    for cand in (attr1, *str(item_name).split("~")):
        s = str(cand).strip().strip("~").strip()
        if s.endswith("-F"):
            s = s[:-2].strip()
        if s and "-F" not in s and not any(n in s.upper() for n in _NOISE) \
                and not s.replace(".", "").isdigit() and len(s) > 2:
            return s.upper()
    return ""


def _cultivar(attr2: str, item_name: str) -> str:
    text = f"{attr2} {item_name}".upper()
    for cv in _CULTIVARS:
        if cv in text:
            return cv
    return ""


def collect(years: list[int]) -> None:
    weekly: dict[str, float] = {}
    all_bb = []
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
            all_bb.append(bb[["exp_num", "exp_rut", "exp_comuna", "region", "qty",
                              "arancel", "item_name", "attr1", "attr2"]])
            print(f"{r['name']}: +{len(bb)} blueberry-UK rows, {bb['qty'].sum():.0f} kg")

    # --- producer + cultivar attribution: the masked RUT leaks the marca/cultivar
    # in the cargo description, so we can NAME the producer for a large share ---
    if all_bb:
        big = pd.concat(all_bb, ignore_index=True)
        big["producer"] = [_clean_producer(a, n) for a, n in zip(big["attr1"], big["item_name"])]
        big["cultivar"] = [_cultivar(a, n) for a, n in zip(big["attr2"], big["item_name"])]
        big["organic"] = big["arancel"].str.strip().eq("08104021")
        named = big[big["producer"] != ""]
        total = big["qty"].sum()
        cov = 100 * named["qty"].sum() / total if total else 0

        prod = (named.groupby("producer")
                .agg(net_kg=("qty", "sum"), n=("qty", "size")).reset_index())
        reg = named.groupby(["producer", "region"])["qty"].sum().reset_index()
        prod["top_region"] = prod["producer"].map(
            reg.sort_values("qty").groupby("producer").tail(1).set_index("producer")["region"])
        cv = named[named["cultivar"] != ""].groupby(["producer", "cultivar"])["qty"].sum().reset_index()
        prod["top_cultivar"] = prod["producer"].map(
            cv.sort_values("qty").groupby("producer").tail(1).set_index("producer")["cultivar"])
        prod = prod.sort_values("net_kg", ascending=False)
        prod["net_kg"] = prod["net_kg"].round(1)
        prod_out = OUT.parent / "chile_uk_blueberry_by_producer.csv"
        prod[["producer", "net_kg", "n", "top_region", "top_cultivar"]].to_csv(prod_out, index=False)

        print(f"\nwrote {prod_out}: {len(prod)} NAMED producers "
              f"({cov:.0f}% of kg named), total {total:.0f} kg")
        print("TOP NAMED PRODUCERS of UK-bound blueberry (name / kg / share / region / cultivar):")
        for _, r in prod.head(15).iterrows():
            print(f"  {r['producer']:24s} {r['net_kg']:>10.0f} kg  {100*r['net_kg']/total:4.1f}%  "
                  f"region={r['top_region']}  cv={r['top_cultivar']}")
        print("cultivar mix (kg):",
              named[named["cultivar"] != ""].groupby("cultivar")["qty"].sum()
              .sort_values(ascending=False).head(8).round(0).to_dict())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(sorted(weekly.items()), columns=["iso_week", "net_kg"])
    # WEEK-LEVEL merge: only weeks we recomputed are replaced; every other week is
    # preserved. A failed/empty download can never wipe committed history.
    if OUT.exists():
        old = pd.read_csv(OUT)
        old = old[~old["iso_week"].isin(new["iso_week"])]
        out = (pd.concat([old, new], ignore_index=True)
               .drop_duplicates("iso_week", keep="last").sort_values("iso_week"))
    else:
        out = new.sort_values("iso_week")
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(out)} weeks total ({len(new)} refreshed this run), "
          f"{out['net_kg'].sum():.0f} kg")


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
