"""How fast news gets into prices, measured three ways.

1. Partial adjustment on the event paths. Each day the price closes a fixed share
   kappa of the gap to its new value, so after the news

       CAR(t) = A * (1 - (1 - kappa)^(t + 1)),   t = 0, 1, 2, ...

   and the half-life, the days until half the move is in, is ln 0.5 / ln(1 - kappa).
2. Daily lead-lag between uranium equities and the Sprott physical trust (2021+):
   do equities today predict the physical price tomorrow, or the reverse?
3. Monthly lead-lag between equities and the IMF spot series (1996+), with the
   equity price averaged over the month the same way spot is, so that averaging
   alone cannot create a lag.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

KAPPAS = np.linspace(0.01, 0.99, 197)


def fit_adjustment(car: np.ndarray) -> tuple[float, float]:
    """Least-squares (A, kappa) for a CAR path starting at day 0. Grid over kappa;
    A has a closed form given kappa."""
    t = np.arange(len(car))
    best = (np.inf, np.nan, np.nan)
    for k in KAPPAS:
        g = 1 - (1 - k) ** (t + 1)
        a = g @ car / (g @ g)
        sse = ((car - a * g) ** 2).sum()
        if sse < best[0]:
            best = (sse, a, k)
    return best[1], best[2]


def half_life(kappa: float) -> float:
    return np.log(0.5) / np.log(1 - kappa)


def adjustment(ar: pd.DataFrame, horizon=20, n_boot=2000, seed=0) -> dict:
    """Fit on the mean signed CAR from day 0 to `horizon`; bootstrap over events."""
    a = ar.loc[:, 0:horizon].to_numpy()
    A, k = fit_adjustment(a.mean(0).cumsum())
    rng = np.random.default_rng(seed)
    hl = []
    for _ in range(n_boot):
        Ab, kb = fit_adjustment(a[rng.integers(0, len(a), len(a))].mean(0).cumsum())
        hl.append(half_life(kb) if Ab > 0 else np.nan)
    hl = np.array(hl)
    return {"A": A, "kappa": k, "half_life": half_life(k),
            "hl_ci": tuple(np.nanpercentile(hl, [5, 95])), "hl_draws": hl}


def cross_corr(x: pd.Series, y: pd.Series, lags=range(-5, 6)) -> pd.Series:
    """corr(x_t, y_{t+k}): positive k with a positive value means x leads y."""
    d = pd.concat([x, y], axis=1).dropna()
    return pd.Series({k: d.iloc[:, 0].corr(d.iloc[:, 1].shift(-k)) for k in lags})


def lead_lag(lead: pd.Series, follow: pd.Series, max_lag=5) -> dict:
    """Regress follow_t on lead_{t-k}, k = 0..max_lag, plus own lags of follow.

    Returns the lead coefficients and the share of their sum at k = 0 (1.0 means
    no delay at all), with HAC-free OLS standard errors (fine for a sketch).
    """
    cols = {f"lead{k}": lead.shift(k) for k in range(max_lag + 1)}
    cols |= {f"own{k}": follow.shift(k) for k in range(1, max_lag + 1)}
    d = pd.concat([follow.rename("y"), pd.DataFrame(cols)], axis=1).dropna()
    X = np.column_stack([np.ones(len(d)), d.drop(columns="y").to_numpy()])
    y = d["y"].to_numpy()
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    cov = np.linalg.inv(X.T @ X) * resid.var(ddof=X.shape[1])
    lb = b[1:max_lag + 2]
    lagged = slice(2, max_lag + 2)  # lead1..leadK
    s = lb[1:].sum()
    se_s = np.sqrt(cov[lagged, lagged].sum())
    return {"coef": pd.Series(lb, index=range(max_lag + 1)),
            "se": pd.Series(np.sqrt(np.diag(cov))[1:max_lag + 2], index=range(max_lag + 1)),
            "lagged_sum": s, "lagged_t": s / se_s,
            "share_now": lb[0] / lb.sum() if lb.sum() > 0 else np.nan, "n": len(d)}


def monthly_pair(px: pd.Series, spot: pd.Series, average=True) -> pd.DataFrame:
    """Equity and spot as monthly log returns. With average=True the equity price is
    averaged over the month like spot is; otherwise it is the month-end close."""
    px = px.dropna().resample("MS")
    eq = px.mean() if average else px.last()
    d = pd.concat([eq.rename("equity"), spot], axis=1).dropna()
    return np.log(d).diff().dropna()
