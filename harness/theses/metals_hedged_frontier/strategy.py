"""PURPOSE: volatility-gated allocation between SPY/TLT and GLD/SLV sleeves.
INPUTS: adjusted-close history through the decision close and a parameter mapping.
OUTPUTS: causal, long-only SPY/TLT/GLD/SLV target weights summing to one.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

ASSETS = ["SPY", "TLT", "GLD", "SLV"]
PPY = 252.0


@dataclass
class FrontierState:
    anchor_metals: float
    minimum_variance_metals: float
    high_risk_metals: float
    raw_coordinate: float
    short_volatility: float
    long_volatility: float
    growth_gap: float


class MetalsHedgedFrontier:
    def __init__(self, params: dict[str, Any]) -> None:
        self.interpolation = str(params.get("interpolation", "sine"))
        self.interpolation_days = int(params.get("interpolation_days", 5))
        self.lookback = int(params.get("lookback", 126))
        self.min_history = int(params.get("min_history", 20))
        self.short_vol_days = int(params.get("short_vol_days", 5))
        self.long_vol_days = int(params.get("long_vol_days", 21))
        self.core_spy = float(params.get("core_spy_weight", 0.60))
        self.metals_gold = float(params.get("metals_gold_weight", 0.70))
        self.reference_metals = float(params.get("reference_metals_weight", 0.20))
        self.min_metals = float(params.get("min_metals_weight", 0.05))
        self.max_metals = float(params.get("max_metals_weight", 0.35))
        self.risk_aversion = float(params.get("risk_aversion", 3.0))
        self.volatility_band = float(params.get("volatility_band", 0.50))
        if self.interpolation not in {"sine", "linear", "polynomial"}:
            raise ValueError("interpolation must be sine, linear, or polynomial")
        if not 0 <= self.min_metals < self.max_metals <= 1:
            raise ValueError("metals bounds must satisfy 0 <= min < max <= 1")

    def asset_weights(self, metals: float) -> np.ndarray:
        core = 1.0 - metals
        return np.array([
            core * self.core_spy,
            core * (1.0 - self.core_spy),
            metals * self.metals_gold,
            metals * (1.0 - self.metals_gold),
        ])

    def _kernel(self, n: int) -> np.ndarray:
        x = np.arange(1, n + 1, dtype=float)
        if self.interpolation == "sine":
            values = np.sin(np.pi * x / (2.0 * n))
        elif self.interpolation == "linear":
            values = x
        else:
            values = x**2
        return values / values.sum()

    def _sleeve_returns(self, returns: pd.DataFrame) -> pd.DataFrame:
        core = returns["SPY"] * self.core_spy + returns["TLT"] * (1.0 - self.core_spy)
        metals = returns["GLD"] * self.metals_gold + returns["SLV"] * (1.0 - self.metals_gold)
        return pd.DataFrame({"core": core, "metals": metals}, index=returns.index)

    def _frontier(self, returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
        sleeves = self._sleeve_returns(returns).iloc[-self.lookback :]
        mu = sleeves.mean().to_numpy(dtype=float) * PPY
        cov = sleeves.cov().to_numpy(dtype=float) * PPY
        ridge = max(float(np.trace(cov)), 1e-8) * 1e-8
        cov = cov + np.eye(2) * ridge
        metals = np.linspace(self.min_metals, self.max_metals, 181)
        weights = np.column_stack([1.0 - metals, metals])
        expected = weights @ mu
        variance = np.einsum("ij,jk,ik->i", weights, cov, weights)
        gmv = int(np.argmin(variance))
        high_return = len(metals) - 1 if mu[1] >= mu[0] else 0
        lo, hi = sorted((gmv, high_return))
        path = np.arange(lo, hi + 1)
        score = expected[path] - 0.5 * self.risk_aversion * variance[path]
        anchor = int(path[int(np.argmax(score))])
        return metals, expected, np.sqrt(np.maximum(variance, 0.0)), gmv, anchor

    def state(self, history: pd.DataFrame) -> FrontierState:
        returns = history[ASSETS].pct_change().dropna()
        if len(returns) < self.min_history:
            r = self.reference_metals
            return FrontierState(r, r, r, 0.0, 0.0, 0.0, 0.0)
        metals, expected, _volatility, gmv_i, anchor_i = self._frontier(returns)
        high_return_i = len(metals) - 1 if expected[-1] >= expected[0] else 0
        anchor_w = self.asset_weights(float(metals[anchor_i]))
        reference_w = self.asset_weights(self.reference_metals)
        short = returns.iloc[-self.short_vol_days :].to_numpy(dtype=float)
        long = returns.iloc[-self.long_vol_days :].to_numpy(dtype=float)
        short_reference = short @ reference_w
        long_reference = long @ reference_w
        short_vol = float(np.std(short_reference, ddof=1) * np.sqrt(PPY))
        long_vol = float(np.std(long_reference, ddof=1) * np.sqrt(PPY))
        anchor_growth = float(np.prod(1.0 + short @ anchor_w) - 1.0)
        reference_growth = float(np.prod(1.0 + short_reference) - 1.0)
        growth_gap = anchor_growth - reference_growth
        scale = max(long_vol * np.sqrt(self.short_vol_days / PPY), 1e-6)
        gate = min(abs(growth_gap) / scale, 1.0)
        surprise = 0.0 if long_vol <= 1e-12 else short_vol / long_vol - 1.0
        raw = float(np.clip(surprise / self.volatility_band, -1.0, 1.0) * gate)
        return FrontierState(float(metals[anchor_i]), float(metals[gmv_i]),
                             float(metals[high_return_i]), raw, short_vol, long_vol, growth_gap)

    def coordinate(self, history: pd.DataFrame) -> float:
        available = min(self.interpolation_days, len(history))
        raw = [self.state(history.iloc[: len(history) - offset]).raw_coordinate
               for offset in range(available - 1, -1, -1)]
        return float(np.dot(self._kernel(available), np.asarray(raw)))

    def weights(self, history: pd.DataFrame) -> pd.Series:
        state = self.state(history)
        coordinate = self.coordinate(history)
        if coordinate >= 0:
            metals = state.anchor_metals + coordinate * (
                state.minimum_variance_metals - state.anchor_metals)
        else:
            metals = state.anchor_metals + (-coordinate) * (
                state.high_risk_metals - state.anchor_metals)
        metals = float(np.clip(metals, self.min_metals, self.max_metals))
        return pd.Series(self.asset_weights(metals), index=ASSETS).reindex(history.columns).fillna(0.0)


def build(params: dict[str, Any]) -> MetalsHedgedFrontier:
    return MetalsHedgedFrontier(params)
