from __future__ import annotations

import pytest

from tradebot.broker.sim import SimBroker


@pytest.fixture
def sim_broker() -> SimBroker:
    return SimBroker(starting_cash=100_000.0)
