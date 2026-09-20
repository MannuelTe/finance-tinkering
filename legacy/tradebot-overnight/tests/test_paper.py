from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tradebot import paper
from tradebot.overnight import OvernightConfig


def _daily(n: int = 260, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.008, n))
    open_ = np.r_[100, close[:-1]] * (1 + rng.normal(0.0006, 0.003, n))
    return pd.DataFrame({"open": open_, "close": close}, index=pd.bdate_range("2025-01-01", periods=n))


def _nav(index: pd.DatetimeIndex, daily_return: float, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    r = daily_return + rng.normal(0, 0.003, len(index))
    return pd.Series(100 * np.cumprod(1 + r), index=index)


@pytest.fixture
def inputs():
    d = _daily()
    rng = np.random.default_rng(9)
    intraday = pd.DataFrame(
        {"intraday_var": rng.uniform(0.5e-4, 3e-4, len(d))}, index=d.index
    )
    baselines = {k: _nav(d.index, 0.0004, s) for s, k in enumerate(["blend_hold", "classic", "spy"])}
    return d, intraday, _nav(d.index, 0.0003, 7), baselines


def test_metrics_of_a_constant_return_series():
    m = paper.metrics(pd.Series(0.001, index=pd.bdate_range("2025-01-01", periods=252)))
    assert m["total_return"] == pytest.approx(1.001**252 - 1)
    assert m["cagr"] == pytest.approx(m["total_return"])  # exactly one year of sessions
    assert m["max_drawdown"] == 0 and m["volatility"] == pytest.approx(0)


def test_metrics_max_drawdown_is_peak_to_trough():
    r = pd.Series([0.10, -0.20, 0.05], index=pd.bdate_range("2025-01-01", periods=3))
    assert paper.metrics(r)["max_drawdown"] == pytest.approx(-0.20)


def test_combine_is_rest_plus_weighted_slice_on_common_dates_only():
    idx = pd.bdate_range("2025-01-01", periods=5)
    rest = pd.Series([0.01, 0.02, -0.01, 0.0, 0.03], index=idx)
    sl = pd.Series([0.001, 0.002, 0.003], index=idx[1:4])
    got = paper.combine(rest, sl, spy_weight=0.27)
    assert list(got.index) == list(idx[1:4])
    assert got.tolist() == pytest.approx([0.02 + 0.27 * 0.001, -0.01 + 0.27 * 0.002, 0.0 + 0.27 * 0.003])


def test_tables_have_the_expected_shape_and_start_at_100(inputs):
    d, intraday, rest_nav, baselines = inputs
    t = paper.build_tables(d, intraday, rest_nav, baselines, 0.27, window=20)
    assert set(t) == {"equity", "returns", "summary", "decisions", "sensitivity_min_weight",
                      "sensitivity_cost", "window"}
    equity = t["equity"].set_index("date")
    assert (equity.iloc[0] == 100.0).all()
    assert list(equity.columns) == list(paper.STRATEGIES)
    assert len(t["sensitivity_min_weight"]) == 6 and len(t["sensitivity_cost"]) == 4
    assert set(t["summary"]["key"]) == set(paper.STRATEGIES)


def test_cash_strategy_is_exactly_the_rest_and_hold_all_uses_the_full_overnight_leg(inputs):
    d, intraday, rest_nav, baselines = inputs
    t = paper.build_tables(d, intraday, rest_nav, baselines, 0.27, window=20, cost_bps=2.0)
    r = t["returns"].set_index("date")
    rest = paper.rest_returns(rest_nav).reindex(r.index)
    pd.testing.assert_series_equal(r["cash"], rest, check_names=False)
    # "always" = rest + 27% of (overnight return - cost) every single decision day
    overnight = (d.open / d.close.shift(1) - 1).reindex(r.index)
    expected = rest + 0.27 * (overnight - 2.0 / 10_000)
    pd.testing.assert_series_equal(r["always"], expected, check_names=False)


def test_vol_aware_trades_no_more_often_than_the_binary_ev_rule(inputs):
    d, intraday, rest_nav, baselines = inputs
    t = paper.build_tables(d, intraday, rest_nav, baselines, 0.27, window=20, min_weight=0.5)
    sens = t["sensitivity_min_weight"].set_index("min_weight")
    assert sens.trade_fraction.is_monotonic_decreasing  # a stricter bar can only skip more days
    assert sens.loc[0.0, "trade_fraction"] >= sens.loc[1.0, "trade_fraction"]


def test_decisions_carry_the_volatility_that_drove_them(inputs):
    d, intraday, rest_nav, baselines = inputs
    t = paper.build_tables(d, intraday, rest_nav, baselines, 0.27, window=20)
    dec = t["decisions"]
    assert {"decision_date", "sale_date", "traded", "raw_weight", "sigma_intraday",
            "next_overnight_return", "slice_return", "intraday_var"} <= set(dec.columns)
    assert (dec["sale_date"] > dec["decision_date"]).all()  # the sale is always after the decision
    traded = dec[dec.traded]
    # a traded day earns weight * (overnight return - cost); a skipped day earns nothing
    assert traded["slice_return"].tolist() == pytest.approx(
        (traded["next_overnight_return"] - 2.0 / 10_000).tolist()
    )
    assert (dec.loc[~dec.traded, "slice_return"] == 0).all()


def test_slice_table_skips_days_without_intraday_data(inputs):
    d, intraday, *_ = inputs
    gappy = intraday["intraday_var"].drop(d.index[100:110])
    tbl = paper.slice_table(d, gappy, OvernightConfig(window=20, cost_bps=2, binary=True, min_weight=0.5))
    assert tbl["intraday_missing"].sum() == 10
    assert (tbl.loc[tbl.intraday_missing, "weight"] == 0).all()
