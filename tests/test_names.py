"""Tests for entity-name canonicalisation + roster matching."""
from nowcast.farm import names


def test_canonicalize_strips_legal_and_cargo_artefacts():
    assert names.canonicalize("COMERCIALIZADORA S&A") == names.canonicalize("S&A")
    assert names.canonicalize("ANGUS SOFT") == "ANGUS"
    assert names.canonicalize("AGRICOLA CATO-F") == "CATO"
    assert names.canonicalize("HORTIFRUT CHILE S.A.") == "HORTIFRUT"


def test_match_score_and_best_match():
    assert names.match_score("HORTIFRUT", "HORTIFRUT S.A.") == 1.0
    roster = ["EXPORTADORA HORTIFRUT S.A.", "AGRICOLA SAN RAFAEL LTDA", "DOLE CHILE"]
    m, s = names.best_match("HORTIFRUT", roster)
    assert m == "EXPORTADORA HORTIFRUT S.A." and s == 1.0
    # an unrelated name stays unmatched
    m2, _ = names.best_match("CUATRO VIENTOS", roster, threshold=0.5)
    assert m2 is None


def test_ampersand_acronym_does_not_false_match():
    # regression: "S&A" must NOT collapse to a shared {AND}/empty token that
    # matched "A&C LTDA". The "&" is kept as part of the token.
    assert "&" in names.canonicalize("S&A")
    assert names.match_score("S&A", "AGRICOLA Y EXPORTADORA A&C LTDA") < 0.5
    # but it still matches its real entry, and HTML-encoded "&" decodes
    assert names.match_score("S&A", "AGRICOLA S&A RINCONADA S.A.") >= 0.5
    assert names.match_score("S&A", "AGRICOLA S&#38;A RINCONADA") >= 0.5
