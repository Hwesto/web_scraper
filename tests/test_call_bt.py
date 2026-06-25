"""The call back-test must separate the validated supply half from the weak
price half and report both honestly."""
from deep.backtest import call_bt


def test_backtest_reports_both_halves():
    r = call_bt.run()
    assert r["n_calls"] > 10
    # supply call is the validated edge -> clearly above coin flip
    assert r["supply_dir_skill_%"] >= 55
    # price call is the weak inference -> reported, near coin flip on free data
    assert r["price_call_dir_skill_%"] is not None
    assert "corr_supply_anom_vs_fwd_price" in r
