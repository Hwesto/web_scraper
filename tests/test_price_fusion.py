"""Validate the price-fusion mechanism is correct.

The real-data result is a null (retail price barely correlates with import
volume), so we must prove that is genuine signal-weakness, not a dead pipe:
when price IS strongly informative, fusing it must measurably improve the
nowcast over HMRC-only. This test injects a clean price = a + b*volume signal
and checks the fused nowcast beats the price-free one.
"""
import numpy as np
import pandas as pd

from deep.model.structural import BlueberryStructuralModel


def _synthetic_volume(n_months=60, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n_months, freq="MS")
    t = np.arange(n_months)
    level = 1000 + 8 * t
    seasonal = 600 * np.sin(2 * np.pi * t / 12) + 250 * np.sin(4 * np.pi * t / 12)
    vol = np.clip(level + seasonal + rng.normal(0, 60, n_months), 0, None)
    return pd.Series(vol, index=idx)


def test_informative_price_improves_nowcast():
    vol = _synthetic_volume()
    # Strong, clean inverse price signal: price = 20 - 0.004*volume + small noise.
    rng = np.random.default_rng(1)
    price = pd.Series(20.0 - 0.004 * vol.values + rng.normal(0, 0.05, len(vol)),
                      index=vol.index)

    err_price, err_noprice = [], []
    months = list(vol.index)
    for i in range(36, len(months)):
        target = months[i]
        key = f"{target.year:04d}-{target.month:02d}"
        model = BlueberryStructuralModel(k_harmonics=2, maxiter=600).fit(
            vol.iloc[:i], price=price)
        mp, _ = model.nowcast(key, use_price=True)
        mn, _ = model.nowcast(key, use_price=False)
        actual = float(vol.loc[target])
        err_price.append(abs(mp - actual))
        err_noprice.append(abs(mn - actual))

    mae_price = float(np.mean(err_price))
    mae_noprice = float(np.mean(err_noprice))
    # A strongly informative price must cut nowcast error materially.
    assert mae_price < 0.8 * mae_noprice, (mae_price, mae_noprice)


def test_price_calibration_recovers_negative_beta():
    vol = _synthetic_volume()
    price = pd.Series(20.0 - 0.004 * vol.values, index=vol.index)
    model = BlueberryStructuralModel(k_harmonics=1, maxiter=300).fit(vol, price=price)
    alpha, beta, _ = model._price_cal
    assert beta < 0                       # correct economic sign
    assert abs(beta - (-0.004)) < 0.002   # roughly recovered
