"""PURPOSE: volatility-gated motion along a rolling SPY/TLT mean-variance frontier.
INPUTS: adjusted-close history through the decision close and a parameter mapping.
OUTPUTS: causal, long-only SPY/TLT target weights summing to one.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

PPY = 252.0


@dataclass
class FrontierState:
    anchor_spy: float
    minimum_variance_spy: float
    high_risk_spy: float
    raw_coordinate: float
    short_volatility: float
    long_volatility: float
    growth_gap: float


class VolatilityFrontier:
    def __init__(self, params: dict[str, Any]) -> None:
        self.interpolation = str(params.get("interpolation", "sine"))
        self.interpolation_days = int(params.get("interpolation_days", 5))
        self.lookback = int(params.get("lookback", 126))
        self.min_history = int(params.get("min_history", 20))
        self.short_vol_days = int(params.get("short_vol_days", 5))
        self.long_vol_days = int(params.get("long_vol_days", 21))
        self.reference_spy = float(params.get("reference_spy_weight", 0.60))
        self.min_spy = float(params.get("min_spy_weight", 0.05))
        self.max_spy = float(params.get("max_spy_weight", 0.95))
        self.risk_aversion = float(params.get("risk_aversion", 3.0))
        self.volatility_band = float(params.get("volatility_band", 0.50))
        if self.interpolation not in {"sine", "linear", "polynomial"}:
            raise ValueError("interpolation must be sine, linear, or polynomial")
        if not 0 <= self.min_spy < self.max_spy <= 1:
            raise ValueError("SPY weight bounds must satisfy 0 <= min < max <= 1")

    def _kernel(self, n: int) -> np.ndarray:
        x = np.arange(1, n + 1, dtype=float)
        if self.interpolation == "sine":
            kernel = np.sin(np.pi * x / (2.0 * n))
        elif self.interpolation == "linear":
            kernel = x
        else:
            kernel = x**2
        return kernel / kernel.sum()

    def _frontier(self, returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
        sample = returns.iloc[-self.lookback :]
        mu = sample.mean().to_numpy(dtype=float) * PPY
        cov = sample.cov().to_numpy(dtype=float) * PPY
        ridge = max(float(np.trace(cov)), 1e-8) * 1e-8
        cov = cov + np.eye(2) * ridge
        spy = np.linspace(self.min_spy, self.max_spy, 181)
        weights = np.column_stack([spy, 1.0 - spy])
        expected = weights @ mu
        variance = np.einsum("ij,jk,ik->i", weights, cov, weights)
        gmv = int(np.argmin(variance))
        high_return = len(spy) - 1 if mu[0] >= mu[1] else 0
        lo, hi = sorted((gmv, high_return))
        path = np.arange(lo, hi + 1)
        score = expected[path] - 0.5 * self.risk_aversion * variance[path]
        anchor = int(path[int(np.argmax(score))])
        return spy, expected, np.sqrt(np.maximum(variance, 0.0)), gmv, anchor

    def state(self, history: pd.DataFrame) -> FrontierState:
        prices = history[["SPY", "TLT"]]
        returns = prices.pct_change().dropna()
        if len(returns) < self.min_history:
            return FrontierState(self.reference_spy, self.reference_spy, self.reference_spy,
                                 0.0, 0.0, 0.0, 0.0)
        spy, expected, _volatility, gmv_i, anchor_i = self._frontier(returns)
        higher_return_i = len(spy) - 1 if expected[-1] >= expected[0] else 0
        anchor_w = np.array([spy[anchor_i], 1.0 - spy[anchor_i]])
        reference_w = np.array([self.reference_spy, 1.0 - self.reference_spy])
        short = returns.iloc[-self.short_vol_days :].to_numpy(dtype=float)
        long = returns.iloc[-self.long_vol_days :].to_numpy(dtype=float)
        short_reference = short @ reference_w
        long_reference = long @ reference_w
        short_vol = float(np.std(short_reference, ddof=1) * np.sqrt(PPY))
        long_vol = float(np.std(long_reference, ddof=1) * np.sqrt(PPY))
        anchor_growth = float(np.prod(1.0 + short @ anchor_w) - 1.0)
        reference_growth = float(np.prod(1.0 + short_reference) - 1.0)
        growth_gap = anchor_growth - reference_growth
        growth_scale = max(long_vol * np.sqrt(self.short_vol_days / PPY), 1e-6)
        gate = min(abs(growth_gap) / growth_scale, 1.0)
        surprise = 0.0 if long_vol <= 1e-12 else short_vol / long_vol - 1.0
        raw = float(np.clip(surprise / self.volatility_band, -1.0, 1.0) * gate)
        return FrontierState(float(spy[anchor_i]), float(spy[gmv_i]),
                             float(spy[higher_return_i]), raw, short_vol, long_vol, growth_gap)

    def coordinate(self, history: pd.DataFrame) -> float:
        available = min(self.interpolation_days, len(history))
        values = []
        for offset in range(available - 1, -1, -1):
            sub = history.iloc[: len(history) - offset]
            values.append(self.state(sub).raw_coordinate)
        return float(np.dot(self._kernel(available), np.asarray(values)))

    def weights(self, history: pd.DataFrame) -> pd.Series:
        state = self.state(history)
        coordinate = self.coordinate(history)
        if coordinate >= 0:
            spy = state.anchor_spy + coordinate * (state.minimum_variance_spy - state.anchor_spy)
        else:
            spy = state.anchor_spy + (-coordinate) * (state.high_risk_spy - state.anchor_spy)
        spy = float(np.clip(spy, self.min_spy, self.max_spy))
        return pd.Series({"SPY": spy, "TLT": 1.0 - spy}).reindex(history.columns).fillna(0.0)


def build(params: dict[str, Any]) -> VolatilityFrontier:
    return VolatilityFrontier(params)
