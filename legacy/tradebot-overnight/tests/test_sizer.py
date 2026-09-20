from __future__ import annotations

from tradebot.broker.base import Position
from tradebot.execution.sizer import size_orders


def test_size_orders_from_flat():
    orders = size_orders(
        target_weights={"SPY": 0.6, "TLT": 0.4},
        positions=[],
        nav=10_000.0,
        last_price={"SPY": 500.0, "TLT": 90.0},
    )
    by_symbol = {o.symbol: o.qty for o in orders}
    assert by_symbol["SPY"] == 12.0
    assert round(by_symbol["TLT"], 4) == round(4000.0 / 90.0, 4)


def test_size_orders_skips_tiny_deltas():
    orders = size_orders(
        target_weights={"SPY": 0.6},
        positions=[Position(symbol="SPY", qty=12.0, avg_price=500.0)],
        nav=10_000.0,
        last_price={"SPY": 500.0},
        min_trade_notional=1.0,
    )
    assert orders == []


def test_size_orders_skips_symbols_without_a_price():
    orders = size_orders(
        target_weights={"SPY": 0.6, "UNKNOWN": 0.4},
        positions=[],
        nav=10_000.0,
        last_price={"SPY": 500.0},
    )
    assert {o.symbol for o in orders} == {"SPY"}


def test_size_orders_whole_shares_truncate_toward_zero():
    orders = size_orders(
        target_weights={"SPY": 0.5},
        positions=[Position(symbol="TLT", qty=10.5, avg_price=90.0)],
        nav=10_000.0,
        last_price={"SPY": 300.0, "TLT": 90.0},
        whole_shares=True,
    )
    by_symbol = {o.symbol: o.qty for o in orders}
    assert by_symbol["SPY"] == 16.0  # 5000/300 = 16.67 -> never overspend
    assert by_symbol["TLT"] == -10.0  # selling 10.5 -> 10, not 11


def test_size_orders_whole_shares_drops_sub_share_deltas():
    orders = size_orders(
        target_weights={"SPY": 0.5},
        positions=[Position(symbol="SPY", qty=16.0, avg_price=300.0)],
        nav=10_000.0,
        last_price={"SPY": 300.0},  # target 16.67, delta 0.67 shares -> nothing to do
        whole_shares=True,
    )
    assert orders == []


def test_size_orders_skips_nan_and_infinite_prices():
    orders = size_orders(
        target_weights={"SPY": 0.5, "TLT": 0.25, "XUT": 0.25},
        positions=[],
        nav=10_000.0,
        last_price={"SPY": 500.0, "TLT": float("nan"), "XUT": float("inf")},
        whole_shares=True,
    )
    assert {o.symbol for o in orders} == {"SPY"}
