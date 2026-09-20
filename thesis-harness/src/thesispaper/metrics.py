"""Performance and estimation maths (pure numpy/pandas).

PURPOSE: returns, wealth, CAGR, vol, Sharpe, drawdown, Gaussian MLE, Kelly, stationary bootstrap.
INPUTS: price DataFrames/Series or simple-return Series (periodic, default 252 per year).
OUTPUTS: floats, Series, or small dataclasses. Sharpe uses zero risk-free rate unless given.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

PPY = 252


def simple_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    return prices.pct_change().iloc[1:]


def log_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    return np.log(prices).diff().iloc[1:]


def wealth(returns: pd.Series, start: float = 1.0) -> pd.Series:
    return start * (1.0 + returns).cumprod()


def total_return(returns: pd.Series) -> float:
    return float((1.0 + returns).prod() - 1.0)


def cagr(returns: pd.Series, ppy: int = PPY) -> float:
    years = len(returns) / ppy
    growth = 1.0 + total_return(returns)
    return float(growth ** (1.0 / years) - 1.0) if years > 0 and growth > 0 else float("nan")


def ann_vol(returns: pd.Series, ppy: int = PPY) -> float:
    return float(returns.std(ddof=1) * np.sqrt(ppy))


def sharpe(returns: pd.Series, rf: float = 0.0, ppy: int = PPY) -> float:
    """Annualised Sharpe of per-period returns; rf is a per-period risk-free rate."""
    ex = np.asarray(returns, dtype=float) - rf
    sd = ex.std(ddof=1)
    return float(ex.mean() / sd * np.sqrt(ppy)) if sd > 0 else float("nan")


def rolling_sharpe(returns: pd.Series, window: int = 126, ppy: int = PPY) -> pd.Series:
    r = returns.rolling(window)
    return r.mean() / r.std(ddof=1) * np.sqrt(ppy)


def drawdown_series(returns: pd.Series) -> pd.Series:
    w = wealth(returns)
    return w / w.cummax().clip(lower=1.0) - 1.0


def max_drawdown(returns: pd.Series) -> float:
    return float(drawdown_series(returns).min())


@dataclass(frozen=True)
class GaussianMLE:
    mu: float
    var: float
    se_mu: float
    se_var: float
    n: int


def gaussian_mle(x: pd.Series | np.ndarray) -> GaussianMLE:
    """MLE of N(mu, s2): mu=mean, s2=mean sq. dev. (1/n); se(mu)=sqrt(s2/n), se(s2)=s2*sqrt(2/n)."""
    a = np.asarray(x, dtype=float)
    n = a.size
    mu = float(a.mean())
    var = float(((a - mu) ** 2).mean())
    return GaussianMLE(mu, var, float(np.sqrt(var / n)), float(var * np.sqrt(2.0 / n)), n)


def kelly(mu: float, var: float) -> float:
    """Continuous-time Kelly approximation f* = mu / sigma^2 (per-period mu, var)."""
    return float(mu / var) if var > 0 else float("nan")


def fractional_kelly(mu: float, var: float, fraction: float = 0.5, cap: float = 1.0) -> float:
    """fraction * f*, clipped to [0, cap] (long-only, leverage cap)."""
    f = kelly(mu, var)
    return float(min(max(fraction * f, 0.0), cap)) if np.isfinite(f) else float("nan")


def stationary_bootstrap_indices(
    n: int, n_boot: int, mean_block: float, rng: np.random.Generator
) -> np.ndarray:
    """Politis-Romano indices, shape (n_boot, n): new block w.p. 1/mean_block, else next index."""
    p = 1.0 / max(mean_block, 1.0)
    idx = np.empty((n_boot, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, n_boot)
    jump = rng.random((n_boot, n)) < p
    fresh = rng.integers(0, n, (n_boot, n))
    for t in range(1, n):
        idx[:, t] = np.where(jump[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def bootstrap_ci(
    x: pd.Series | np.ndarray, stat: str = "sharpe", n_boot: int = 1000,
    mean_block: float = 10.0, alpha: float = 0.05, seed: int = 0, ppy: int = PPY,
) -> tuple[float, float]:
    """Percentile CI of an annualised 'sharpe' or 'mean' via stationary bootstrap (seeded)."""
    if stat not in ("sharpe", "mean"):
        raise ValueError("stat must be 'sharpe' or 'mean'")
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    samples = a[stationary_bootstrap_indices(a.size, n_boot, mean_block, rng)]
    m = samples.mean(axis=1)
    vals = m * ppy if stat == "mean" else m / samples.std(axis=1, ddof=1) * np.sqrt(ppy)
    lo, hi = np.nanquantile(vals, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)
