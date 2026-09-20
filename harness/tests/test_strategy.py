from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tradebot.strategy.base import StrategyContext
from tradebot.strategy.constant import ConstantWeightStrategy


def test_constant_weight_strategy_returns_fixed_weights():
    strategy = ConstantWeightStrategy(weights={"SPY": 0.6, "TLT": 0.4})
    ctx = StrategyContext(positions=[], nav=10_000.0)
    weights = strategy.target_weights(datetime.now(UTC), ctx)
    assert weights == {"SPY": 0.6, "TLT": 0.4}


def test_constant_weight_strategy_rejects_over_allocation():
    with pytest.raises(ValueError):
        ConstantWeightStrategy(weights={"SPY": 0.7, "TLT": 0.4})
