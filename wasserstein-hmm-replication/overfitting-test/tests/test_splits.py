"""Offline tests for the purged random-block splitter and the blocked order selector."""

import numpy as np

from overfit_hmm.config import OverfitConfig
from overfit_hmm.selection import select_order_blocked
from overfit_hmm.splits import blocked_splits, gather


def _layout(seed: int, n: int = 3000):
    rng = np.random.default_rng(seed)
    return blocked_splits(n, 80, 80, 3, 60, 120, rng)


def test_last_days_are_a_test_block() -> None:
    _, tests = _layout(0)
    assert tests[-1] == (2920, 3000)
    assert len(tests) == 4


def test_gaps_are_purged_and_sets_disjoint() -> None:
    for seed in range(25):
        train, tests = _layout(seed)
        for t0, t1 in tests:
            for a, b in train:
                assert b <= t0 - 60 or a >= t1 + 60  # >= 60 days between train and any test
        for (_, b1), (a2, _) in zip(tests, tests[1:]):
            assert a2 >= b1  # test blocks never overlap
        assert all(b - a >= 120 for a, b in train)


def test_layout_is_random_but_seeded() -> None:
    assert _layout(1) == _layout(1)
    assert _layout(1) != _layout(2)


def test_gather_lengths() -> None:
    x = np.arange(20.0).reshape(-1, 1)
    stacked, lengths = gather(x, [(0, 5), (10, 13)])
    assert lengths == [5, 3] and stacked.shape == (8, 1)


def test_select_order_blocked_returns_candidate() -> None:
    rng = np.random.default_rng(0)
    x = np.vstack([rng.normal(0, 1, (700, 3)), rng.normal(3, 0.5, (700, 3))])
    config = OverfitConfig(candidate_states=(2, 3), hmm_iterations=10)
    k, scores = select_order_blocked(x, config)
    assert k in (2, 3) and set(scores) == {2, 3}
