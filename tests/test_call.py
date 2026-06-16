"""Smoke tests for the 'this week's call' hero panel."""
import datetime as _dt

from nowcast import call


def test_in_season_call_has_supply_and_action():
    c = call.weekly_call(_dt.date(2025, 1, 20))
    assert c["origin"] == "Chile" and c["landing_month"] == "2025-01"
    if c["in_season"]:
        assert c["supply_signal"] in (call._LONG, call._SHORT, call._NORMAL)
        assert c["price_lean"] in ("UP", "DOWN", "FLAT")
        assert isinstance(c["action"], str) and c["action"]
        assert "CALL" in call.render(c)


def test_off_season_is_honest_not_a_fake_call():
    c = call.weekly_call(_dt.date(2026, 7, 1))   # austral winter -> Chile not shipping
    assert c["in_season"] is False
    assert "off-season" in call.render(c)


def test_action_matches_lean():
    c = call.weekly_call(_dt.date(2025, 2, 18))
    lean_to_word = {"DOWN": "move volume", "UP": "lock", "FLAT": "hold"}
    assert lean_to_word[c["price_lean"]] in c["action"]
