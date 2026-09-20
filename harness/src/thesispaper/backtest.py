"""Backtest engine: rebalanced weights, turnover costs, strictly no lookahead.

PURPOSE: turn a Strategy and a price panel into net daily returns, weights, turnover and NAV.
INPUTS: prices DataFrame[date x ticker], Strategy, costs_bps per unit turnover, rebalance schedule.
OUTPUTS: `BacktestResult`.

NO-LOOKAHEAD RULE: the return earned on day t is P_t/P_{t-1}-1. Target weights for day t are
decided by `strategy.weights(prices.iloc[:t])`, i.e. only closes up to t-1, and applied to day t's
return. Between rebalances weights drift with prices. Cost on a rebalance day =
turnover * costs_bps/1e4 with turnover = sum |target - drifted weight| (first day buys from cash).
`lookahead_check` perturbs prices from a chosen day on and verifies earlier weights are unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from thesispaper.strategy import Strategy


@dataclass(frozen=True)
class BacktestResult:
    returns: pd.Series  # net of costs
    gross_returns: pd.Series
    weights: pd.DataFrame  # weights applied to each day's return (post-rebalance)
    turnover: pd.Series
    nav: pd.Series  # starts at 1.0 on the first price date


def is_rebalance_day(prev: pd.Timestamp | None, cur: pd.Timestamp, rebalance: str) -> bool:
    if prev is None or rebalance == "daily":
        return True
    if rebalance == "weekly":
        return cur.isocalendar()[:2] != prev.isocalendar()[:2]
    if rebalance == "monthly":
        return (cur.year, cur.month) != (prev.year, prev.month)
    raise ValueError(f"unknown rebalance {rebalance!r}")


def _validated(w: pd.Series, cols: pd.Index) -> np.ndarray:
    arr = w.reindex(cols).fillna(0.0).to_numpy(dtype=float)
    if not np.isfinite(arr).all() or (arr < -1e-12).any() or arr.sum() > 1.0 + 1e-9:
        raise ValueError(f"invalid target weights (need finite, >=0, sum<=1): {w.to_dict()}")
    return arr


def run(
    prices: pd.DataFrame, strategy: Strategy, costs_bps: float = 0.0, rebalance: str = "daily"
) -> BacktestResult:
    rets = prices.pct_change().to_numpy()
    n, k = prices.shape
    drift = np.zeros(k)
    applied = np.zeros((n - 1, k))
    net, gross, turn = np.zeros(n - 1), np.zeros(n - 1), np.zeros(n - 1)
    prev: pd.Timestamp | None = None
    for t in range(1, n):
        cur = prices.index[t]
        if is_rebalance_day(prev, cur, rebalance):
            target = _validated(strategy.weights(prices.iloc[:t]), prices.columns)
            turn[t - 1] = np.abs(target - drift).sum()
            drift = target
        prev = cur
        applied[t - 1] = drift
        g = float(drift @ rets[t])
        gross[t - 1] = g
        net[t - 1] = g - turn[t - 1] * costs_bps / 1e4
        drift = drift * (1.0 + rets[t]) / (1.0 + g)
    idx = prices.index[1:]
    r = pd.Series(net, idx, name="strategy")
    nav = pd.concat([pd.Series([1.0], [prices.index[0]]), (1 + r).cumprod()])
    return BacktestResult(
        r, pd.Series(gross, idx), pd.DataFrame(applied, idx, prices.columns),
        pd.Series(turn, idx), nav.rename("nav"),
    )


def lookahead_check(
    prices: pd.DataFrame, factory: Callable[[], Strategy], rebalance: str = "daily",
    cut: int | None = None, seed: int = 0,
) -> bool:
    """True iff weights up to and including day `cut` are unchanged when later prices change."""
    n = len(prices)
    cut = cut if cut is not None else n // 2
    rng = np.random.default_rng(seed)
    bumped = prices.copy()
    bumped.iloc[cut + 1 :] *= rng.uniform(0.5, 1.5, size=bumped.iloc[cut + 1 :].shape)
    a = run(prices, factory(), 0.0, rebalance).weights
    b = run(bumped, factory(), 0.0, rebalance).weights
    return bool(np.allclose(a.iloc[:cut].to_numpy(), b.iloc[:cut].to_numpy(), atol=1e-12))
