"""Entity-name canonicalisation + roster matching.

Two jobs: (1) collapse the messy free-text producer marcas from the cargo
description (LAFRUT vs 'LA FRUT F-'; ANGUS vs ANGUS SOFT; S&A vs COMERCIALIZADORA
S&A) into canonical names -- the dedup the spec's canonical_entities step owed;
(2) match our named producers against an external roster (e.g. the SAG list of
~71 blueberry predios approved for China export) to tie our UK flow to named +
located + CSG-coded orchards for the overlap.
"""
from __future__ import annotations

import html
import re

_LEGAL = [r"\bSOCIEDAD\b", r"\bCOMERCIAL(IZADORA)?\b", r"\bEXPORTADORA?\b",
          r"\bAGR[ÍI]COLA\b", r"\bAGRONEGOCIOS\b", r"\bFRUT[ÍI]COLA\b",
          r"\bSERVICIOS\b", r"\bINVERSIONES\b", r"\bLTDA\.?\b", r"\bLIMITADA\b",
          r"\bSPA\b", r"\bS\.?A\.?\b", r"\bE\.?I\.?R\.?L\.?\b", r"\bY\s+CIA\b",
          r"\bGROUP\b", r"\bCHILE\b"]
_SUFFIX = [r"\s*SOFT$", r"\s*-?F-?$", r"\bF$"]   # cargo-desc artefacts


def canonicalize(name: str) -> str:
    s = html.unescape(str(name)).upper().strip().strip("~").strip()
    for pat in _SUFFIX:
        s = re.sub(pat, "", s).strip()
    # Keep "&" as part of the token (S&A stays "S&A"): expanding it to the
    # conjunction "AND" collapses acronym names to a shared {AND} false-positive,
    # and dropping it makes "S&A" collide with the "S.A." legal suffix.
    s = s.replace(".", "").replace(",", " ")
    for pat in _LEGAL:
        s = re.sub(pat, " ", s)
    s = re.sub(r"[^A-Z0-9& ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokens(name: str) -> set:
    return {t for t in canonicalize(name).split() if len(t) > 1 or "&" in t}


def match_score(a: str, b: str) -> float:
    """Jaccard token overlap of two canonicalised names (0..1)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def best_match(name: str, roster: list[str], threshold: float = 0.5):
    """Best roster entry for `name` above threshold, else None."""
    best, score = None, 0.0
    for cand in roster:
        s = match_score(name, cand)
        if s > score:
            best, score = cand, s
    return (best, round(score, 2)) if score >= threshold else (None, round(score, 2))
