"""Offline tests for thesispaper (synthetic prices only)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from thesispaper import metrics as m
from thesispaper.backtest import lookahead_check, run
from thesispaper.cli import main
from thesispaper.data import synthetic_prices
from thesispaper.spec import SpecError, load_spec, parse_spec
from thesispaper.strategy import BuyHold, ConstantMix, load_strategy

RAW = {
    "title": "T", "slug": "demo", "summary": "s", "universe": ["A", "B"], "benchmark": "A",
    "start": "2020-01-01", "strategy": {"module": "builtin:constant_mix", "params": {}},
}


def test_synthetic_deterministic() -> None:
    a = synthetic_prices(["A", "B"], "2020-01-01", seed=3)
    b = synthetic_prices(["A", "B"], "2020-01-01", seed=3)
    pd.testing.assert_frame_equal(a, b)
    assert not a["A"].equals(a["B"])


def test_returns_wealth_drawdown() -> None:
    r = pd.Series([0.1, -0.1, 0.05, 0.0])
    w = m.wealth(r)
    assert w.iloc[-1] == pytest.approx(1.1 * 0.9 * 1.05)
    assert m.total_return(r) == pytest.approx(w.iloc[-1] - 1)
    assert m.max_drawdown(r) == pytest.approx(-0.1)
    assert m.cagr(pd.Series([0.0] * 252)) == pytest.approx(0.0)
    p = pd.Series([100.0, 110.0])
    assert m.log_returns(p).iloc[0] == pytest.approx(np.log(1.1))


def test_sharpe_and_mle_kelly() -> None:
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0.001, 0.01, 5000))
    assert m.sharpe(x) == pytest.approx(x.mean() / x.std(ddof=1) * np.sqrt(252))
    e = m.gaussian_mle(x)
    assert e.mu == pytest.approx(x.mean()) and e.se_mu == pytest.approx(np.sqrt(e.var / 5000))
    assert m.kelly(e.mu, e.var) == pytest.approx(e.mu / e.var)
    assert m.fractional_kelly(0.01, 0.0001, 0.5, cap=2.0) == 2.0
    assert m.fractional_kelly(-0.01, 0.0001) == 0.0


def test_bootstrap_seeded_and_covers() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(0.0005, 0.01, 1000)
    a = m.bootstrap_ci(x, "sharpe", 300, seed=5)
    assert a == m.bootstrap_ci(x, "sharpe", 300, seed=5)
    assert a[0] < m.sharpe(pd.Series(x)) < a[1]
    lo, hi = m.bootstrap_ci(x, "mean", 300, seed=5)
    assert lo < x.mean() * 252 < hi


def test_backtest_timing_and_costs() -> None:
    idx = pd.bdate_range("2021-01-04", periods=4)
    p = pd.DataFrame({"A": [100.0, 110.0, 99.0, 99.0]}, index=idx)

    class Follow:  # weights depend on the last known return only
        def weights(self, h: pd.DataFrame) -> pd.Series:
            up = h["A"].iloc[-1] > h["A"].iloc[-2] if len(h) > 1 else True
            return pd.Series({"A": 1.0 if up else 0.0})

    bt = run(p, Follow(), 0.0)
    assert bt.returns.iloc[0] == pytest.approx(0.10)
    assert bt.returns.iloc[1] == pytest.approx(-0.10)
    assert bt.weights.iloc[2]["A"] == 0.0
    costly = run(p, ConstantMix({}), 100.0)  # 1% per unit turnover, only first day trades
    assert costly.turnover.iloc[0] == pytest.approx(1.0)
    assert costly.returns.iloc[0] == pytest.approx(0.10 - 0.01)
    assert costly.turnover.iloc[1:].abs().sum() == pytest.approx(0.0)


def test_buy_hold_drift_and_rebalance_schedule() -> None:
    p = synthetic_prices(["A", "B"], "2020-01-01", n_years=1.0)
    bh = run(p, BuyHold({"weights": {"A": 0.5, "B": 0.5}}), 0.0, "daily")
    assert bh.turnover.iloc[1:].max() < 1e-9
    monthly = run(p, ConstantMix({}), 0.0, "monthly")
    assert (monthly.turnover > 1e-12).sum() < 20


def test_engine_only_shows_past_and_check_passes() -> None:
    p = synthetic_prices(["A", "B"], "2020-01-01", n_years=1.0)
    seen: list[pd.Timestamp] = []

    class Spy:
        def weights(self, h: pd.DataFrame) -> pd.Series:
            seen.append(h.index[-1])
            return pd.Series(0.5, index=h.columns)

    run(p, Spy(), 0.0)
    # weights for day t see only rows strictly before t
    assert all(last < day for last, day in zip(seen, p.index[1:], strict=True))

    class Momentum:
        def weights(self, h: pd.DataFrame) -> pd.Series:
            up = h.iloc[-1] > h.iloc[max(0, len(h) - 5)]
            return up.astype(float) / max(len(h.columns), 1)

    assert lookahead_check(p, lambda: Momentum(), "weekly")


def test_spec_validation(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    assert parse_spec(RAW, d).rebalance == "daily"
    with pytest.raises(SpecError) as ei:
        parse_spec({**RAW, "rebalance": "hourly", "costs_bps": -1, "universe": []}, d)
    assert "rebalance" in str(ei.value) and "universe" in str(ei.value)
    with pytest.raises(SpecError, match="folder name"):
        parse_spec({**RAW, "slug": "other"}, d)
    with pytest.raises(SpecError, match="not found"):
        load_spec("nope", tmp_path)


def test_strategy_loading(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    spec = parse_spec(RAW, d)
    assert isinstance(load_strategy(spec), ConstantMix)
    (d / "strategy.py").write_text(
        "import pandas as pd\nclass S:\n    def weights(self, h):\n"
        "        return pd.Series(0.5, index=h.columns)\ndef build(params):\n    return S()\n"
    )
    spec2 = parse_spec({**RAW, "strategy": {"module": "strategy.py"}}, d)
    assert load_strategy(spec2).weights(pd.DataFrame({"A": [1.0]})).iloc[0] == 0.5
    bad = parse_spec({**RAW, "strategy": {"module": "builtin:nope"}}, d)
    with pytest.raises(ValueError):
        load_strategy(bad)


def test_cli_new_check_run(tmp_path: Path) -> None:
    root = str(tmp_path)
    assert main(["new", "demo", "--root", root, "--synthetic"]) == 0
    assert main(["new", "demo", "--root", root]) == 1
    assert main(["check", "demo", "--root", root]) == 0
    assert main(["run", "demo", "--root", root]) == 0
    d = tmp_path / "theses" / "demo"
    res = json.loads((d / "results.json").read_text())
    assert res["sample"]["n_obs"] > 500 and res["hypotheses"][0]["id"] == "H1"
    assert res["bootstrap"]["sharpe"]["low"] < res["bootstrap"]["sharpe"]["high"]
    tex = (d / "numbers.tex").read_text()
    for name in ("CAGR", "Sharpe", "MaxDD", "SharpeCILow", "StartDate", "CostBps"):
        assert f"\\newcommand{{\\{name}}}" in tex
    assert (d / "figures" / "fig_equity.pdf").exists()
    assert (d / "figures" / "fig_sensitivity.png").exists()
