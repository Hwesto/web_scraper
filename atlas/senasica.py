"""Mexico's SENASICA register of berry orchards authorised to export -- the
SAG-China analogue, and the atlas's first free *entity-level* overlay.

Most countries keep their phytosanitary export registry gated (Spain CEXVEG,
US PCIT, ...). Mexico publishes it: SENASICA's "Predios de berries inscritos
para exportar a China" lists every registered orchard by name, SAGARPA registry
code, area (ha), municipality, state and fruit. This wires the named-orchard
data type the project values (cf. Chile's SAG China roster) for a second origin.

The list is a bilingual (ES/中文) PDF on the gob.mx CMS; we parse the text table
(pypdf -- no key, verified parseable 2026-06: 71 orchards, blueberry + other
berries). Snapshot-style source (the published file is dated); the URL changes
when SENASICA republishes -- bump REPORT_URL then (cf. the USDA Peru fetcher).
Committed to data/atlas/mx_registered_orchards.csv.
"""
from __future__ import annotations

import io
import re
import urllib.request

import pandas as pd

from atlas import ATLAS_DIR

CACHE = ATLAS_DIR / "mx_registered_orchards.csv"
# "Predios de berries inscritos para exportar a China" (SENASICA, gob.mx CMS).
REPORT_URL = ("https://www.gob.mx/cms/uploads/attachment/file/864021/"
              "Lista_de_Predios_inscritos__para_exportar_a_China_2018.pdf")
DESTINATION = "China"
_COLS = ["registro", "predio", "area_ha", "municipio", "estado", "fruto",
         "destination", "source"]

# Mexican states, longest-first, to peel the estado off the "municipio estado" run.
_STATES = ["Baja California Sur", "Baja California", "San Luis Potosí", "Nuevo León",
           "Quintana Roo", "Aguascalientes", "Campeche", "Chiapas", "Chihuahua",
           "Coahuila", "Colima", "Durango", "Guanajuato", "Guerrero", "Hidalgo",
           "Jalisco", "Michoacán", "Morelos", "Nayarit", "Oaxaca", "Puebla",
           "Querétaro", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala",
           "Veracruz", "Yucatán", "Zacatecas", "México"]
# row: No · PRE-code · predio · area · "municipio estado"<中文state> · fruto<中文>
_ROW = re.compile(
    r"^(\d+)\s+(PRE\S+)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+"
    r"([A-Za-zÁÉÍÓÚáéíóúÑñ .]+?)\s*[一-鿿]+\s*"
    r"([A-Za-zÁÉÍÓÚáéíóúÑñ]+)[一-鿿]+\s*$")


def _split_state(municipio_estado: str) -> tuple[str, str]:
    for s in _STATES:
        if municipio_estado == s:
            return "", s
        if municipio_estado.endswith(" " + s):
            return municipio_estado[: -len(s)].strip(), s
    return municipio_estado, ""


def _parse_text(text: str) -> pd.DataFrame:
    """Parse the extracted PDF text into the orchard table (offline-testable)."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not re.match(r"^\d+\s+PRE", line):
            continue
        m = _ROW.match(line)
        if not m:
            continue
        _no, registro, predio, area, muni_est, fruto = m.groups()
        municipio, estado = _split_state(muni_est)
        rows.append({"registro": registro, "predio": predio.strip(),
                     "area_ha": float(area), "municipio": municipio, "estado": estado,
                     "fruto": fruto, "destination": DESTINATION,
                     "source": "SENASICA predios de berries (China)"})
    return pd.DataFrame(rows, columns=_COLS)


def parse(pdf_bytes: bytes) -> pd.DataFrame:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    df = _parse_text(text)
    if df.empty:
        raise RuntimeError("no orchard rows parsed -- PDF layout may have changed")
    return df


def refresh(url: str = REPORT_URL, local: str | None = None) -> pd.DataFrame:
    if local:
        data = open(local, "rb").read()
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=60).read()
    df = parse(data)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False)
    return df


def load(fruit: str | None = None) -> pd.DataFrame:
    if not CACHE.exists():
        return pd.DataFrame(columns=_COLS)
    df = pd.read_csv(CACHE)
    if fruit is not None:
        df = df[df["fruto"] == fruit].reset_index(drop=True)
    return df


def summary(fruit: str = "Arándano") -> pd.DataFrame:
    """Registered-orchard count and area (ha) by state, for one fruit."""
    df = load(fruit)
    if df.empty:
        return df
    g = df.groupby("estado").agg(orchards=("registro", "size"),
                                 area_ha=("area_ha", "sum")).reset_index()
    return g.sort_values("area_ha", ascending=False).reset_index(drop=True)


if __name__ == "__main__":                             # python -m atlas.senasica
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="parse a local PDF instead of downloading")
    df = refresh(local=ap.parse_args().local)
    bb = df[df["fruto"] == "Arándano"]
    print(f"parsed {len(df)} registered berry orchards ({len(bb)} blueberry) -> {CACHE}")
    print("\nblueberry orchards by state:")
    print(summary("Arándano").to_string(index=False))
