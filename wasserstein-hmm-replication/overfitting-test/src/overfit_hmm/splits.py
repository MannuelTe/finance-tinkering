"""PURPOSE: purged random-block train/test layouts for time series.
INPUTS: sample length and block/gap sizes.
OUTPUTS: disjoint train segments and test blocks as half-open (start, stop) index pairs.

Layout, oldest to newest:  |train|gap|TEST|gap|train|gap|TEST|gap|train| ... |gap|TEST(last)|
"""

import numpy as np

Interval = tuple[int, int]


def _merge(zones: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, stop in sorted(zones):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], stop))
        else:
            merged.append((start, stop))
    return merged


def _complement(zones: list[Interval], n: int) -> list[Interval]:
    segments, cursor = [], 0
    for start, stop in _merge(zones):
        if start > cursor:
            segments.append((cursor, start))
        cursor = max(cursor, stop)
    if cursor < n:
        segments.append((cursor, n))
    return segments


def blocked_splits(
    n: int, holdout: int, block_len: int, n_random: int, gap: int, min_segment: int,
    rng: np.random.Generator, max_tries: int = 20_000,
) -> tuple[list[Interval], list[Interval]]:
    """Draw random test blocks plus the final `holdout` days; purge `gap` days around each.

    Rejection sampling: a draw is kept only if every remaining train segment has at least
    `min_segment` observations, so the HMM always sees a usable stretch of history.
    """
    final = (n - holdout, n)
    for _ in range(max_tries):
        starts = rng.integers(0, n - holdout - gap - block_len + 1, size=n_random)
        tests = sorted((int(s), int(s) + block_len) for s in starts) + [final]
        zones = [(max(0, a - gap), min(n, b + gap)) for a, b in tests]
        train = _complement(zones, n)
        overlap = any(a2 < b1 for (_, b1), (a2, _) in zip(tests, tests[1:]))
        if not overlap and train and all(b - a >= min_segment for a, b in train):
            return train, tests
    raise ValueError("no feasible blocked split; shrink blocks/gaps or lengthen the history")


def gather(x: np.ndarray, intervals: list[Interval]) -> tuple[np.ndarray, list[int]]:
    """Stack the intervals into one array and return the per-sequence lengths for hmmlearn."""
    return np.vstack([x[a:b] for a, b in intervals]), [b - a for a, b in intervals]
