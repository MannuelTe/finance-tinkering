"""The replication's Wasserstein-HMM and KNN backtests, with the paper's unstated choices exposed.

This is `wasserstein_hmm.backtest.run_hmm` with two extra switches that are not fields of
`ReplicationConfig`:

* `cov_type`: HMM emission covariance ("full" in the replication; "diag" is the other
  common choice), patched into `wasserstein_hmm.models._hmm` for the duration of a run;
* `mixture_cov`: add the between-template spread of means to the blended covariance
  (the exact covariance of a mixture; the paper and the replication leave it out);
* `outcome`: "simple" (replication) or "log": the paper defines the portfolio return as
  weights times *log* returns, and estimates regime moments on them;
* `regime_cov`: "diag" (replication: shrink 10% towards the diagonal) or "lw" (Ledoit-Wolf
  shrinkage intensity, as the paper uses for KNN).

With the defaults it reproduces the replication exactly (checked in tests). Everything else
(K range, windows, templates, optimizer...) is a `ReplicationConfig` field and is varied by
`dataclasses.replace`. The window to backtest is `oos_start`..`oos_end` of the config, so the
same code runs the tuning window (2019-2023) and the paper's test window (2023-2026).
"""

from __future__ import annotations

from contextlib import contextmanager

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import ledoit_wolf_shrinkage
from wasserstein_hmm import backtest as bt_module
from wasserstein_hmm import data as data_module
from wasserstein_hmm import models
from wasserstein_hmm.backtest import Backtest, _summarize_arrays
from wasserstein_hmm.config import ReplicationConfig
from wasserstein_hmm.models import fit_regime_model, initialize_templates, select_order
from wasserstein_hmm.optimize import solve_mvo

_ORIGINAL_MD = data_module.market_data
_ORIGINAL_CM = models.conditional_moments


def market_data(prices, config, outcome="simple"):
    outcomes, features = _ORIGINAL_MD(prices, config)
    if outcome == "log":
        outcomes = np.log(prices).diff().reindex(outcomes.index)
    return outcomes, features


def lw_conditional_moments(posterior, returns, shrinkage):
    """Posterior-weighted moments with a Ledoit-Wolf shrinkage intensity (towards a scaled
    identity) estimated on the weighted, centred returns."""
    k, n = posterior.shape[1], returns.shape[1]
    means, covs = np.zeros((k, n)), np.zeros((k, n, n))
    fallback = np.cov(returns, rowvar=False) + np.eye(n) * 1e-8
    for state in range(k):
        w = posterior[:, state]
        if w.sum() < n + 2:
            covs[state] = fallback
            continue
        w = w / w.sum()
        means[state] = w @ returns
        c = returns - means[state]
        emp = (c * w[:, None]).T @ c
        eff = 1.0 / np.sum(w ** 2)                      # effective sample size
        z = c * np.sqrt(w[:, None] * eff)                # rows whose plain covariance = emp
        delta = ledoit_wolf_shrinkage(z, assume_centered=True)
        mu = np.trace(emp) / n
        covs[state] = (1 - delta) * emp + delta * mu * np.eye(n) + np.eye(n) * 1e-8
    return means, covs


@contextmanager
def covariance_type(kind: str):
    """Temporarily make every HMM the replication builds use `kind` covariances."""
    original = models._hmm

    def patched(k, config, iterations=None):
        return GaussianHMM(n_components=k, covariance_type=kind,
                           n_iter=iterations or config.hmm_iterations, min_covar=1e-4,
                           random_state=config.random_seed, tol=1e-3)

    models._hmm = patched
    try:
        yield
    finally:
        models._hmm = original


@contextmanager
def outcome_type(outcome: str):
    """Make the replication's own KNN backtest use the chosen outcome returns too."""
    bt_module.market_data = lambda p, c: market_data(p, c, outcome)
    try:
        yield
    finally:
        bt_module.market_data = _ORIGINAL_MD


def run_knn(prices, config: ReplicationConfig, outcome="simple") -> Backtest:
    with outcome_type(outcome):
        return bt_module.run_knn(prices, config)


def run_hmm(prices, config: ReplicationConfig, cov_type="full", mixture_cov=False,
            outcome="simple", regime_cov="diag") -> Backtest:
    models.conditional_moments = lw_conditional_moments if regime_cov == "lw" else _ORIGINAL_CM
    try:
        with covariance_type(cov_type):
            # models.* read model.covars_, which hmmlearn (0.3) returns as full matrices for
            # both "full" and "diag", so nothing else needs to change.
            return _run(prices, config, mixture_cov, outcome)
    finally:
        models.conditional_moments = _ORIGINAL_CM


def _run(prices, config, mixture_cov, outcome) -> Backtest:
    outcomes, features = market_data(prices, config, outcome)
    oos = features.loc[config.oos_start:config.oos_end]
    pre = features.index < oos.index[0]
    bank = initialize_templates(features.loc[pre].to_numpy(), outcomes.loc[pre].to_numpy(), config)
    previous = np.full(len(prices.columns), 1 / len(prices.columns))
    fitted = None
    current_k = config.template_count
    dates, gross, weights, turnover, regimes, orders = [], [], [], [], [], []
    for step, date in enumerate(oos.index):
        history = features.index < date
        x_hist = features.loc[history].to_numpy()
        y_hist = outcomes.loc[history].to_numpy()
        select_now = fitted is None or step % config.order_selection_frequency == 0
        refit_now = fitted is None or step % config.refit_frequency == 0 or select_now
        if refit_now:
            if select_now:
                scaler = StandardScaler().fit(x_hist)
                current_k, _ = select_order(scaler.transform(x_hist), config)
            fitted = fit_regime_model(x_hist, y_hist, current_k, bank, config)
        probs = fitted.filter(features.loc[date].to_numpy())
        if len(probs) < config.template_count:
            probs = np.pad(probs, (0, config.template_count - len(probs)))
        mean = probs @ bank.return_means
        covariance = np.tensordot(probs, bank.return_covariances, axes=(0, 0))
        if mixture_cov:
            dev = bank.return_means - mean
            covariance = covariance + (probs[:, None] * dev).T @ dev
        target = solve_mvo(mean, covariance, previous, config.risk_aversion,
                           config.turnover_penalty, config.max_weight)
        dates.append(date)
        gross.append(float(target @ outcomes.loc[date].to_numpy()))
        weights.append(target.copy())
        turnover.append(float(0.5 * np.abs(target - previous).sum()))
        regimes.append(int(np.argmax(probs)))
        orders.append(current_k)
        previous = target
    return _summarize_arrays(dates, gross, weights, turnover, prices.columns, config,
                             regimes, orders)


__all__ = ["run_hmm", "run_knn"]
