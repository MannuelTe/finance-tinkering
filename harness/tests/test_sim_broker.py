from __future__ import annotations

from tradebot.broker.base import Order
from tradebot.broker.sim import SimBroker


def test_place_buy_updates_position_and_cash(sim_broker: SimBroker):
    sim_broker.set_price("SPY", 500.0)
    sim_broker.place([Order(symbol="SPY", qty=10.0)])

    positions = sim_broker.positions()
    assert len(positions) == 1
    assert positions[0].symbol == "SPY"
    assert positions[0].qty == 10.0
    assert positions[0].avg_price == 500.0
    assert sim_broker.nav() == 100_000.0  # cash down, holdings up, NAV unchanged


def test_place_sell_reduces_position(sim_broker: SimBroker):
    sim_broker.set_price("SPY", 500.0)
    sim_broker.place([Order(symbol="SPY", qty=10.0)])
    sim_broker.place([Order(symbol="SPY", qty=-4.0)])

    positions = {p.symbol: p for p in sim_broker.positions()}
    assert positions["SPY"].qty == 6.0
