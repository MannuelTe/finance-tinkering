"""Strategy interface.

PURPOSE: Strategy interface.
INPUTS:  StrategyContext (positions, NAV) and a timestamp.
OUTPUTS: target weights, symbol -> fraction of NAV.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from tradebot.broker.base import Position


@dataclass(frozen=True)
class StrategyContext:
    positions: list[Position]
    nav: float


class Strategy(Protocol):
    """Strategies return target *weights*, never orders — sizing and rebalancing stay in
    execution/sizer.py so the same strategy code runs unchanged in backtest and live."""

    def target_weights(self, asof: datetime, ctx: StrategyContext) -> dict[str, float]: ...
