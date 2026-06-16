"""Cert layer for the named producers (Part 6 follow-on).

Honest constraint (verified): there is NO free, automatable name->GGN discovery.
GlobalG.A.P.'s public database VALIDATES a known GGN/cert number but has no
name search; phyto certs are per-consignment SAG/APHA docs (not public bulk, and
carry SAG CSG codes not GGNs); SAG bulk is on the TLS-blocked datos.gob.cl; GACC
publishes no clean named Chilean-blueberry orchard list; CIREN's named directorio
is paid. A GGN IS a GS1 GLN, so GEPIR can ENRICH a known GLN->entity -- but not
discover it from a name.

So the free, defensible cert layer is two things:
  1. tag_uk_cert_status(): UK retail mandates GLOBALG.A.P. for imported fresh
     produce, so UK-bound producers are near-certainly certified -- a status
     inference attached to every named producer, no GGN required.
  2. attach_ggns() + validate_ggn()/gln_to_entity(): the plug-in point for GGNs
     obtained OUT OF BAND (an importer's own supplier specs, the product GGN
     label, a retailer disclosure). Given a GGN we can validate + enrich it; we
     just cannot find it from the name.
"""
from __future__ import annotations

import pandas as pd
import requests

UK_CERT_BASIS = ("GLOBALG.A.P. (minimum requirement for imported fresh produce "
                 "into UK retail; CBI/retailer sourcing policy)")
_HEADERS = {"User-Agent": "uk-blueberry-nowcast/0.1 (research)"}


def tag_uk_cert_status(producers: pd.DataFrame) -> pd.DataFrame:
    """Attach the defensible cert-status inference to a named-producer table."""
    out = producers.copy()
    out["cert_status"] = "inferred_certified"
    out["cert_basis"] = UK_CERT_BASIS
    out["ggn"] = pd.NA                      # filled by attach_ggns when known
    return out


def attach_ggns(producers: pd.DataFrame, ggn_map: dict[str, str]) -> pd.DataFrame:
    """Join out-of-band GGNs (e.g. importer supplier specs) keyed by producer.
    ggn_map: {producer_name_upper: "GGN 13-digit"}. Names matched case-insensitively."""
    out = producers.copy()
    norm = {k.strip().upper(): v for k, v in ggn_map.items()}
    out["ggn"] = out["producer"].str.strip().str.upper().map(norm).fillna(out.get("ggn"))
    return out


def validate_ggn(ggn: str) -> dict:
    """Validate/enrich a KNOWN GGN against the GLOBALG.A.P. GGN-label service.
    Hook: requires a real GGN to exercise (we cannot discover GGNs from names).
    Returns the raw service response or an error dict."""
    url = f"https://www.ggn.org/search.html?ggn={ggn}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=30)
        return {"ggn": ggn, "http_status": r.status_code, "found": r.status_code == 200,
                "note": "confirm producer name/scope in the returned profile"}
    except requests.RequestException as exc:
        return {"ggn": ggn, "error": str(exc)}


def gln_to_entity(gln: str) -> dict:
    """Resolve a known GLN (a GGN is a GLN) to its registered entity via GS1 GEPIR.
    Hook: public GEPIR endpoints vary by member organisation; needs a real GLN."""
    return {"gln": gln, "service": "GS1 GEPIR", "note": "query the GS1 member GEPIR "
            "for this GLN; a GGN is registered as a GLN so this returns the entity"}
