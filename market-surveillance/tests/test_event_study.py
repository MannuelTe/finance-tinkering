import numpy as np
import pandas as pd
import pytest

from marketsurv.surveillance.event_study import pre_event_screen, screen_events


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


def test_rejects_unsorted_observations():
    stock, mkt, ev = make_stock()
    with pytest.raises(ValueError, match="sorted"):
        pre_event_screen(stock.iloc[::-1], mkt, ev)


def test_empty_batch_result_has_stable_schema():
    events = pd.DataFrame({"ticker": ["MISSING"], "event_date": ["2026-01-05"]})
    result = screen_events(events, {}, pd.Series(dtype=float, index=pd.DatetimeIndex([])))
    assert list(result.columns) == [
        "ticker",
        "event_date",
        "n_est",
        "alpha",
        "beta",
        "car",
        "car_t",
        "volume_z",
        "flagged",
    ]


def test_missing_event_volume_is_not_scored():
    stock, market, event_date = make_stock()
    event_position = stock.index.get_loc(event_date)
    stock.loc[stock.index[event_position - 1], "volume"] = np.nan
    assert pre_event_screen(stock, market, event_date) is None
