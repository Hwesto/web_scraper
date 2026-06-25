"""Light tests for the whole-market fusion helpers (no network/model fit)."""
from deep.volume import uk_total


def test_week_to_month_uses_thursday():
    # 2024-W05 Thursday is 2024-02-01 -> February.
    assert uk_total._week_month("2024-W05") == "2024-02"
    assert uk_total._week_month("2024-W01") == "2024-01"


def test_major_and_deep_sea_sets_are_coherent():
    # every deep-sea lane we claim is also a modelled major origin
    assert uk_total.DEEP_SEA <= set(uk_total.MAJORS)
    # the big four UK suppliers are all modelled
    for o in ["Morocco", "Peru", "South Africa", "Chile"]:
        assert o in uk_total.MAJORS
