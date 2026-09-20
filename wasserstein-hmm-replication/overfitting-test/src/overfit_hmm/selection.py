"""PURPOSE: choose the number of HMM states by purged random-block validation.
INPUTS: standardized feature history and an OverfitConfig.
OUTPUTS: selected order and per-order penalized held-out log-likelihood.

Drop-in replacement for wasserstein_hmm.models.select_order (same signature and return type).
"""

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

from wasserstein_hmm.models import _hmm  # pylint: disable=protected-access

from .config import OverfitConfig
from .splits import blocked_splits, gather


def select_order_blocked(x: np.ndarray, config: OverfitConfig) -> tuple[int, dict[int, float]]:
    # Layout is a deterministic function of (seed, history length): reproducible, yet it
    # moves every time the history grows, so no single lucky layout drives the choice.
    rng = np.random.default_rng([config.random_seed, len(x)])
    train_seg, test_seg = blocked_splits(
        len(x), config.holdout_days, config.block_len, config.random_blocks,
        config.gap_days, config.min_segment, rng,
    )
    train, train_len = gather(x, train_seg)
    test, test_len = gather(x, test_seg)
    scaler = StandardScaler().fit(train)  # train-only scaling: the test blocks never leak in
    train, test = scaler.transform(train), scaler.transform(test)
    d = x.shape[1]
    scores: dict[int, float] = {}
    for k in config.candidate_states:
        try:
            model: GaussianHMM = _hmm(k, config, max(25, config.hmm_iterations // 2))
            model.fit(train, lengths=train_len)  # Baum-Welch over separate sequences
            params = k * (d + d * (d + 1) / 2) + k * k
            held_out = model.score(test, lengths=test_len) / len(test)
            scores[k] = float(held_out - config.complexity_penalty * params)
        except (ValueError, np.linalg.LinAlgError):
            scores[k] = -np.inf
    return max(scores, key=scores.get), scores
