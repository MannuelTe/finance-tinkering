import numpy as np
import pandas as pd

from uransig import insider


def _market(run_up=0.0, vol_mult=1.0, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=600)
    spy = rng.normal(0, 0.01, len(idx))
    x = 1.2 * spy + rng.normal(0, 0.01, len(idx))
    vol = np.exp(rng.normal(13, 0.3, len(idx)))
    pos = 500
    x[pos - 10:pos] += run_up / 10
    vol[pos - 10:pos] *= vol_mult
    ret = pd.DataFrame({"X": x, "SPY": spy}, index=idx)
    return ret, pd.DataFrame({"X": vol}, index=idx), pos


def test_quiet_window_is_not_flagged():
    # seed 0 happens to draw a 3-sigma noise run in the window: the false-flag problem itself
    ret, vol, pos = _market(seed=1)
    fp = insider.footprint(ret, insider.log_volume(vol, ret.index), pos, ["X"], ["SPY"])
    assert abs(fp["car_t"]) < 3 and fp["vol_z"] < 2


def test_informed_run_up_is_flagged_and_limits_make_sense():
    ret, vol, pos = _market(run_up=0.15, vol_mult=3.0)
    fp = insider.footprint(ret, insider.log_volume(vol, ret.index), pos, ["X"], ["SPY"])
    assert fp["car_t"] > 3 and fp["vol_z"] > 2
    # 1% daily noise -> 10-day sd ~3.2%, so a flag needs a run-up of ~9.5%
    assert 0.07 < fp["min_runup"] < 0.12
    assert 1.5 < fp["min_vol_x"] < 2.2  # exp(2 * 0.3)
