import numpy as np
import pandas as pd

from marketsurv.surveillance.event_study import pre_event_screen


def make_stock(n=400, runup=0.0, vol_boost=0.0, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-01", periods=n)
    mkt = pd.Series(rng.normal(0, 0.01, n), idx)
    ret = 0.0002 + 1.1 * mkt + rng.normal(0, 0.01, n)
    volume = np.exp(rng.normal(13, 0.3, n))
    event_pos = n - 5
    ret[event_pos - 10 : event_pos] += runup / 10  # spread the run-up over the 10 days before
    volume[event_pos - 10 : event_pos] *= np.exp(vol_boost)
    return pd.DataFrame({"ret": ret, "volume": volume}, idx), mkt, idx[event_pos]


def test_runup_with_volume_is_flagged():
    stock, mkt, ev = make_stock(runup=0.12, vol_boost=1.0)
    res = pre_event_screen(stock, mkt, ev)
    assert res is not None and res.flagged and res.car_t > 3 and res.volume_z > 2


def test_quiet_stock_is_not_flagged():
    stock, mkt, ev = make_stock()
    res = pre_event_screen(stock, mkt, ev)
    assert res is not None and not res.flagged


def test_short_history_returns_none():
    stock, mkt, ev = make_stock(n=100)
    assert pre_event_screen(stock, mkt, ev) is None
