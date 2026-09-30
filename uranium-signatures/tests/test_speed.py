import numpy as np
import pandas as pd

from uransig import speed


def test_fit_recovers_kappa():
    t = np.arange(21)
    car = 0.08 * (1 - (1 - 0.3) ** (t + 1))
    a, k = speed.fit_adjustment(car)
    assert abs(a - 0.08) < 1e-3 and abs(k - 0.3) < 0.01
    assert abs(speed.half_life(0.5) - 1.0) < 1e-12


def test_lead_lag_finds_a_one_day_lead():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(size=3000))
    y = 0.5 * x.shift(1).fillna(0) + pd.Series(rng.normal(scale=0.5, size=3000))
    r = speed.lead_lag(x, y, 3)
    assert abs(r["coef"][1] - 0.5) < 0.05 and r["lagged_t"] > 10
    assert r["share_now"] < 0.1


def test_averaging_creates_autocorrelation():
    """Working (1960): averaging a random walk over each period gives period-to-period
    changes with first-order autocorrelation near 0.25."""
    rng = np.random.default_rng(1)
    walk = pd.Series(rng.normal(size=21 * 4000).cumsum(),
                     index=pd.bdate_range("1900-01-01", periods=21 * 4000))
    avg = walk.groupby(np.arange(len(walk)) // 21).mean()
    assert abs(avg.diff().dropna().autocorr(1) - 0.25) < 0.04
