"""Offline unit tests for the Wasserstein-HMM replication components."""

import numpy as np
import pandas as pd

from wasserstein_hmm.config import ReplicationConfig
from wasserstein_hmm.data import market_data
from wasserstein_hmm.models import wasserstein2
from wasserstein_hmm.optimize import solve_mvo


def test_wasserstein_identity_and_symmetry() -> None:
    mean_a, mean_b = np.array([0.0, 1.0]), np.array([1.0, 0.0])
    cov_a, cov_b = np.eye(2), np.diag([2.0, 0.5])
    assert abs(wasserstein2(mean_a, cov_a, mean_a, cov_a)) < 1e-10
    assert np.isclose(wasserstein2(mean_a, cov_a, mean_b, cov_b),
                      wasserstein2(mean_b, cov_b, mean_a, cov_a))  # pylint: disable=arguments-out-of-order


def test_features_are_lagged() -> None:
    index = pd.bdate_range("2020-01-01", periods=90)
    prices = pd.DataFrame({ticker: 100 * np.exp(np.arange(90) * 0.001) for ticker in
                           ("SPY", "TLT", "GLD", "USO", "UUP")}, index=index)
    config = ReplicationConfig()
    _, before = market_data(prices, config)
    changed = prices.copy()
    changed.iloc[-1] *= 2
    _, after = market_data(changed, config)
    assert np.allclose(before.loc[index[-1]], after.loc[index[-1]])


def test_optimizer_is_feasible() -> None:
    previous = np.full(5, 0.2)
    weights = solve_mvo(
        np.array([0.001, 0.0005, 0.0002, -0.0001, 0.0003]),
        np.eye(5) * 0.0001, previous, 3.0, 0.0001, 0.6,
    )
    assert np.isclose(weights.sum(), 1.0)
    assert (weights >= 0).all()
    assert (weights <= 0.6 + 1e-9).all()

