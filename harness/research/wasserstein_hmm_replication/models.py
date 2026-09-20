"""PURPOSE: Gaussian-HMM fitting, predictive order choice, and Wasserstein templates.
INPUTS: causal feature histories and corresponding realized asset returns.
OUTPUTS: fitted HMM state plus persistent template-conditioned return moments.
"""

from dataclasses import dataclass

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

from .config import ReplicationConfig


def _psd_sqrt(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh((matrix + matrix.T) / 2)
    return (vectors * np.sqrt(np.clip(values, 0.0, None))) @ vectors.T


def wasserstein2(
    mean_a: np.ndarray, cov_a: np.ndarray, mean_b: np.ndarray, cov_b: np.ndarray,
) -> float:
    root_b = _psd_sqrt(cov_b)
    middle = _psd_sqrt(root_b @ cov_a @ root_b)
    return float((mean_a - mean_b) @ (mean_a - mean_b) + np.trace(cov_a + cov_b - 2 * middle))


def _hmm(k: int, config: ReplicationConfig, iterations: int | None = None) -> GaussianHMM:
    return GaussianHMM(
        n_components=k, covariance_type="full", n_iter=iterations or config.hmm_iterations,
        min_covar=1e-4, random_state=config.random_seed, tol=1e-3,
    )


def select_order(x: np.ndarray, config: ReplicationConfig) -> tuple[int, dict[int, float]]:
    split = len(x) - config.validation_days
    train, validation = x[:split], x[split:]
    scores: dict[int, float] = {}
    d = x.shape[1]
    for k in config.candidate_states:
        try:
            model = _hmm(k, config, max(25, config.hmm_iterations // 2)).fit(train)
            params = k * (d + d * (d + 1) / 2) + k * k
            scores[k] = float(model.score(validation) / len(validation) - config.complexity_penalty * params)
        except (ValueError, np.linalg.LinAlgError):
            scores[k] = -np.inf
    return max(scores, key=scores.get), scores


def conditional_moments(
    posterior: np.ndarray, returns: np.ndarray, shrinkage: float,
) -> tuple[np.ndarray, np.ndarray]:
    k, n = posterior.shape[1], returns.shape[1]
    means, covariances = np.zeros((k, n)), np.zeros((k, n, n))
    fallback = np.cov(returns, rowvar=False) + np.eye(n) * 1e-8
    for state in range(k):
        weights = posterior[:, state]
        total = weights.sum()
        if total < n + 2:
            covariances[state] = fallback
            continue
        weights = weights / total
        means[state] = weights @ returns
        centered = returns - means[state]
        empirical = (centered * weights[:, None]).T @ centered
        target = np.diag(np.diag(empirical))
        covariances[state] = (1 - shrinkage) * empirical + shrinkage * target + np.eye(n) * 1e-8
    return means, covariances


@dataclass
class TemplateBank:
    feature_means: np.ndarray
    feature_covariances: np.ndarray
    return_means: np.ndarray
    return_covariances: np.ndarray
    eta: float

    def map_and_update(
        self, means: np.ndarray, covariances: np.ndarray,
        return_means: np.ndarray, return_covariances: np.ndarray,
    ) -> np.ndarray:
        mapping = np.empty(len(means), dtype=int)
        for state in range(len(means)):
            distances = [
                wasserstein2(means[state], covariances[state], self.feature_means[g], self.feature_covariances[g])
                for g in range(len(self.feature_means))
            ]
            group = int(np.argmin(distances))
            mapping[state] = group
            e = self.eta
            self.feature_means[group] = (1 - e) * self.feature_means[group] + e * means[state]
            self.feature_covariances[group] = (1 - e) * self.feature_covariances[group] + e * covariances[state]
            self.return_means[group] = (1 - e) * self.return_means[group] + e * return_means[state]
            self.return_covariances[group] = (1 - e) * self.return_covariances[group] + e * return_covariances[state]
        return mapping


@dataclass
class FittedRegimeModel:
    model: GaussianHMM
    scaler: StandardScaler
    mapping: np.ndarray
    alpha: np.ndarray

    def filter(self, raw_feature: np.ndarray) -> np.ndarray:
        scaled = self.scaler.transform(raw_feature.reshape(1, -1))
        likelihood = self.model._compute_likelihood(scaled)[0]
        posterior = (self.alpha @ self.model.transmat_) * likelihood
        self.alpha = posterior / max(posterior.sum(), 1e-300)
        probs = np.zeros(int(self.mapping.max()) + 1)
        np.add.at(probs, self.mapping, self.alpha)
        return probs


def fit_regime_model(
    x: np.ndarray, returns: np.ndarray, k: int, bank: TemplateBank, config: ReplicationConfig,
) -> FittedRegimeModel:
    scaler = StandardScaler().fit(x)
    scaled = scaler.transform(x)
    model = _hmm(k, config).fit(scaled)
    posterior = model.predict_proba(scaled)
    ret_means, ret_covs = conditional_moments(posterior, returns, config.covariance_shrinkage)
    raw_means = model.means_ * scaler.scale_ + scaler.mean_
    raw_covs = np.array([
        cov * scaler.scale_[:, None] * scaler.scale_[None, :] for cov in model.covars_
    ])
    mapping = bank.map_and_update(raw_means, raw_covs, ret_means, ret_covs)
    alpha = model.predict_proba(scaled[-min(252, len(scaled)):])[-1]
    return FittedRegimeModel(model, scaler, mapping, alpha)


def initialize_templates(
    x: np.ndarray, returns: np.ndarray, config: ReplicationConfig,
) -> TemplateBank:
    scaler = StandardScaler().fit(x)
    scaled = scaler.transform(x)
    model = _hmm(config.template_count, config).fit(scaled)
    posterior = model.predict_proba(scaled)
    ret_means, ret_covs = conditional_moments(posterior, returns, config.covariance_shrinkage)
    raw_means = model.means_ * scaler.scale_ + scaler.mean_
    raw_covs = np.array([
        cov * scaler.scale_[:, None] * scaler.scale_[None, :] for cov in model.covars_
    ])
    order = np.argsort(raw_means[:, 0])
    return TemplateBank(raw_means[order], raw_covs[order], ret_means[order], ret_covs[order], config.template_smoothing)

