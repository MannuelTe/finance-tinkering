from __future__ import annotations

import pytest

from tradebot import config
from tradebot.broker.base import Bar, Fill, Order, Position
from tradebot.execution.runner import prices_in_base, run_once
from tradebot.strategy.constant import ConstantWeightStrategy


class FakeBroker:
    """Multi-currency stand-in: prices in native currency, NAV in EUR, records placed orders."""

    def __init__(
        self,
        prices: dict[str, float],
        fx: dict[str, float],
        nav: float = 100_000.0,
        working: set[str] | None = None,
        closed: set[str] | None = None,
    ):
        self._prices, self._fx, self._nav = prices, fx, nav
        self._working = working or set()
        self._closed = closed or set()
        self.placed: list[Order] = []

    def is_connected(self) -> bool:
        return True

    def nav(self) -> float:
        return self._nav

    def positions(self) -> list[Position]:
        return []

    def open_order_symbols(self) -> set[str]:
        return set(self._working)

    def is_market_open(self, symbol: str) -> bool:
        return symbol not in self._closed

    def price(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def fx_rate(self, currency: str, base: str) -> float:
        return 1.0 if currency == base else self._fx[currency]

    def bars(self, symbol: str, lookback_days: int) -> list[Bar]:
        return []

    def place(self, orders: list[Order]) -> list[Fill]:
        self.placed.extend(orders)
        return []


@pytest.fixture(autouse=True)
def _permissive_risk(monkeypatch):
    monkeypatch.setattr(config.settings, "max_notional", 1_000_000)
    monkeypatch.setattr(config.settings, "kill_switch", False)
    monkeypatch.setattr(config.settings, "base_currency", "EUR")


def test_prices_are_converted_to_base_currency():
    broker = FakeBroker({"TLT": 500.0, "EXSA": 60.0, "XUT": 40.0}, {"USD": 0.85, "CAD": 0.62})
    prices = prices_in_base(broker, {"TLT", "EXSA", "XUT"})
    assert prices == pytest.approx({"TLT": 425.0, "EXSA": 60.0, "XUT": 24.8})


def test_unregistered_or_unpriced_symbols_are_left_alone():
    broker = FakeBroker({"TLT": 500.0, "OTHER": 10.0}, {"USD": 0.85})
    prices = prices_in_base(broker, {"TLT", "OTHER", "EXSA"})  # OTHER unregistered, EXSA unpriced
    assert set(prices) == {"TLT"}


def test_orders_are_sized_against_base_currency_prices():
    # 10% of 100k EUR = 10k EUR. TLT is 500 USD = 425 EUR -> 23 whole shares (23.5 truncated).
    # Sizing on the raw USD price would have bought 20, i.e. 15% too few.
    broker = FakeBroker({"TLT": 500.0, "XUT": 40.0}, {"USD": 0.85, "CAD": 0.62})
    run_once(broker, ConstantWeightStrategy({"TLT": 0.10, "XUT": 0.05}))
    qty = {o.symbol: o.qty for o in broker.placed}
    assert qty["TLT"] == 23.0
    assert qty["XUT"] == 201.0  # 5000 EUR / (40 CAD * 0.62) = 201.6


def test_nan_prices_and_fx_rates_are_skipped():
    broker = FakeBroker({"TLT": float("nan"), "EXSA": 60.0, "XUT": 40.0}, {"USD": 0.85, "CAD": float("nan")})
    assert prices_in_base(broker, {"TLT", "EXSA", "XUT"}) == {"EXSA": 60.0}


def test_symbols_with_a_working_order_get_no_new_order():
    broker = FakeBroker(
        {"TLT": 500.0, "XUT": 40.0}, {"USD": 0.85, "CAD": 0.62}, working={"TLT"}
    )
    strategy = ConstantWeightStrategy({"TLT": 0.10, "XUT": 0.05})
    run_once(broker, strategy)
    assert {o.symbol for o in broker.placed} == {"XUT"}  # TLT already has an order in flight


def test_repeated_cycles_do_not_stack_orders_while_one_is_working():
    broker = FakeBroker({"TLT": 500.0}, {"USD": 0.85})
    strategy = ConstantWeightStrategy({"TLT": 0.10})
    run_once(broker, strategy)
    assert len(broker.placed) == 1
    broker._working = {"TLT"}  # the order is now working at the broker, position unchanged
    for _ in range(3):
        run_once(broker, strategy)
    assert len(broker.placed) == 1


def test_failure_to_read_open_orders_places_nothing():
    class Unknown(FakeBroker):
        def open_order_symbols(self) -> set[str]:
            raise ConnectionError("cannot read open orders")

    broker = Unknown({"TLT": 500.0}, {"USD": 0.85})
    with pytest.raises(ConnectionError):
        run_once(broker, ConstantWeightStrategy({"TLT": 0.10}))
    assert broker.placed == []


def test_symbols_on_a_closed_market_get_no_order():
    broker = FakeBroker(
        {"TLT": 500.0, "XUT": 40.0}, {"USD": 0.85, "CAD": 0.62}, closed={"XUT"}
    )
    run_once(broker, ConstantWeightStrategy({"TLT": 0.10, "XUT": 0.05}))
    assert {o.symbol for o in broker.placed} == {"TLT"}
