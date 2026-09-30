import numpy as np
import pandas as pd

from uransig import study


def _market(n=5000, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n)
    spy = rng.normal(0, 0.01, n)
    return idx, spy, rng


def _paths(shape, n_events=12, seed=0, noise=0.002):
    """Synthetic stock with beta 1.5 and a known response `shape(day)` at each event."""
    idx, spy, rng = _market(seed=seed)
    stock = 1.5 * spy + rng.normal(0, noise, len(idx))
    days = np.arange(400, 400 + 350 * n_events, 350)  # no overlap with estimation windows
    for d in days:
        for k in range(-study.PRE, study.POST + 1):
            stock[d + k] += shape(k)
    ret = pd.DataFrame({"X": stock, "SPY": spy}, index=idx)
    ev = pd.DataFrame({"date": idx[days], "sign": 1.0})
    ar, _ = study.event_paths(ret, ev, ["X"], ["SPY"])
    return ar


def test_jump_is_fast():
    ar = _paths(lambda k: 0.10 if k == 0 else 0.0)
    s = study.signature(ar)
    assert abs(s["jump"] - 0.10) < 0.01
    assert s["speed"] > 0.9


def test_drift_is_slow():
    ar = _paths(lambda k: 0.005 if 0 <= k <= 20 else 0.0)
    s = study.signature(ar)
    assert abs(s["car_0_20"] - 0.105) < 0.01
    assert s["speed"] < 0.2


def test_symmetry_detects_different_speeds():
    # 2% daily idiosyncratic noise, about what uranium equities show
    fast = _paths(lambda k: 0.10 if k == 0 else 0.0, seed=1, noise=0.02)
    slow = _paths(lambda k: 0.005 if 0 <= k <= 20 else 0.0, seed=2, noise=0.02)
    sym = study.symmetry_test(fast, slow, n_boot=500)
    assert sym.ci["jump"][0] > 0
    same = study.symmetry_test(
        fast, _paths(lambda k: 0.10 if k == 0 else 0.0, seed=3, noise=0.02), n_boot=500)
    assert same.p["jump"] > 0.01  # same shape: no strong evidence of a difference


def test_after_close_news_moves_day0():
    idx = pd.bdate_range("2020-01-06", periods=10)  # Monday start
    dates = pd.Series(pd.to_datetime(["2020-01-10", "2020-01-10", "2020-01-11"]))
    pos = study.align(dates, idx, ["pre", "post", "post"])
    assert list(idx[pos].strftime("%m-%d")) == ["01-10", "01-13", "01-13"]  # Saturday: no extra shift
