"""PURPOSE: solve the paper's long-only transaction-cost-aware mean-variance program.
INPUTS: daily mean/covariance estimates, prior weights, and optimizer coefficients.
OUTPUTS: feasible portfolio weights.
"""

import numpy as np
from scipy.optimize import minimize


def solve_mvo(
    mean: np.ndarray,
    covariance: np.ndarray,
    previous: np.ndarray,
    risk_aversion: float,
    turnover_penalty: float,
    max_weight: float,
) -> np.ndarray:
    n = len(mean)
    covariance = (covariance + covariance.T) / 2 + np.eye(n) * 1e-9
    start = np.r_[previous, np.abs(previous - previous)]

    def objective(z: np.ndarray) -> float:
        w, u = z[:n], z[n:]
        return float(risk_aversion * w @ covariance @ w - mean @ w + turnover_penalty * u.sum())

    def gradient(z: np.ndarray) -> np.ndarray:
        w = z[:n]
        return np.r_[2 * risk_aversion * covariance @ w - mean, np.full(n, turnover_penalty)]

    constraints = [
        {"type": "eq", "fun": lambda z: z[:n].sum() - 1.0},
        {"type": "ineq", "fun": lambda z: z[n:] - (z[:n] - previous)},
        {"type": "ineq", "fun": lambda z: z[n:] + (z[:n] - previous)},
    ]
    result = minimize(
        objective, start, jac=gradient, method="SLSQP", constraints=constraints,
        bounds=[(0.0, max_weight)] * n + [(0.0, 1.0)] * n,
        options={"ftol": 1e-12, "maxiter": 250},
    )
    if not result.success:
        return previous.copy()
    weights = np.clip(result.x[:n], 0.0, max_weight)
    return weights / weights.sum()

