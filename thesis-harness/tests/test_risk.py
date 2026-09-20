from __future__ import annotations

from tradebot import config
from tradebot.broker.base import Order
from tradebot.risk import check_orders


def test_check_orders_rejects_over_notional(monkeypatch):
    monkeypatch.setattr(config.settings, "max_notional", 100)
    monkeypatch.setattr(config.settings, "kill_switch", False)

    orders = [Order(symbol="SPY", qty=1.0)]
    result = check_orders(orders, nav=10_000.0, last_price={"SPY": 500.0})
    assert result.approved == []
    assert result.rejected[0][0] == orders[0]


def test_check_orders_kill_switch(monkeypatch):
    monkeypatch.setattr(config.settings, "kill_switch", True)

    orders = [Order(symbol="SPY", qty=1.0)]
    result = check_orders(orders, nav=10_000.0, last_price={"SPY": 500.0})
    assert result.approved == []


def test_check_orders_approves_within_limits(monkeypatch):
    monkeypatch.setattr(config.settings, "max_notional", 1000)
    monkeypatch.setattr(config.settings, "kill_switch", False)

    orders = [Order(symbol="SPY", qty=1.0)]
    result = check_orders(orders, nav=10_000.0, last_price={"SPY": 500.0})
    assert result.approved == orders
    assert result.rejected == []
