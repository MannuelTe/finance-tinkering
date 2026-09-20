from __future__ import annotations

from datetime import datetime

from tradebot.strategy.base import StrategyContext


class ConstantWeightStrategy:
    """Trivial first strategy: always target the same fixed weights, regardless of asof/ctx."""

    def __init__(self, weights: dict[str, float]) -> None:
        total = sum(weights.values())
        if total > 1.0 + 1e-9:
            raise ValueError(f"weights sum to {total}, must be <= 1.0")
        self._weights = dict(weights)

    def target_weights(self, asof: datetime, ctx: StrategyContext) -> dict[str, float]:
        return dict(self._weights)
