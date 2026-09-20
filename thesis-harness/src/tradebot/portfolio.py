"""Generic portfolio-weight helpers.

PURPOSE: parse, validate and normalize target weights (symbol -> fraction of NAV).
INPUTS:  a mapping of weights, or a "SYM:0.6,SYM2:0.4" string.
OUTPUTS: clean weight dicts; raises ValueError on invalid input.
"""

from __future__ import annotations

import math
from collections.abc import Mapping


def parse_weights(raw: str) -> dict[str, float]:
    """Parse "SPY:0.6,TLT:0.4" into {"SPY": 0.6, "TLT": 0.4}."""
    weights: dict[str, float] = {}
    for pair in raw.split(","):
        if not pair.strip():
            continue
        symbol, _, weight = pair.partition(":")
        if not weight:
            raise ValueError(f"expected SYMBOL:WEIGHT, got {pair!r}")
        weights[symbol.strip()] = float(weight)
    return weights


def validate_weights(weights: Mapping[str, float], max_total: float = 1.0) -> dict[str, float]:
    """Return a copy of `weights` after checking every weight is finite and non-negative and the
    total does not exceed `max_total` (a small tolerance is allowed)."""
    for symbol, w in weights.items():
        if not math.isfinite(w) or w < 0:
            raise ValueError(f"invalid weight for {symbol}: {w}")
    if sum(weights.values()) > max_total + 1e-9:
        raise ValueError(f"weights sum to {sum(weights.values()):.4f}, above {max_total}")
    return dict(weights)


def normalize_weights(weights: Mapping[str, float], total: float = 1.0) -> dict[str, float]:
    """Rescale non-negative weights so they sum to `total`."""
    validate_weights(weights, max_total=math.inf)
    s = sum(weights.values())
    if s <= 0:
        raise ValueError("weights sum to zero")
    return {k: v * total / s for k, v in weights.items()}
