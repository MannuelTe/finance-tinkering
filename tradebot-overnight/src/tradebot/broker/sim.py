from __future__ import annotations

from datetime import UTC, datetime

from tradebot.broker.base import Bar, Fill, Order, Position


class SimBroker:
    """In-memory broker for backtests and dry runs. Implements the same Protocol as IBKRBroker.

    Fills happen instantly at whatever price was last set via set_price() — there is no
    slippage or partial-fill modeling here, this is a sizing/execution-logic sandbox, not
    a fill simulator.
    """

    def __init__(self, starting_cash: float = 100_000.0) -> None:
        self._cash = starting_cash
        self._positions: dict[str, Position] = {}
        self._last_price: dict[str, float] = {}
        self._fx: dict[str, float] = {}

    def is_connected(self) -> bool:
        return True

    def is_market_open(self, symbol: str) -> bool:
        return True

    def open_order_symbols(self) -> set[str]:
        return set()  # fills are instant, so nothing is ever left working

    def price(self, symbol: str) -> float | None:
        return self._last_price.get(symbol)

    def set_fx(self, currency: str, rate: float) -> None:
        self._fx[currency] = rate

    def fx_rate(self, currency: str, base: str) -> float:
        return 1.0 if currency == base else self._fx.get(currency, 1.0)

    def set_price(self, symbol: str, price: float) -> None:
        self._last_price[symbol] = price

    def nav(self) -> float:
        holdings = sum(p.qty * self._last_price.get(p.symbol, p.avg_price) for p in self._positions.values())
        return self._cash + holdings

    def positions(self) -> list[Position]:
        return [p for p in self._positions.values() if p.qty != 0]

    def place(self, orders: list[Order]) -> list[Fill]:
        fills: list[Fill] = []
        now = datetime.now(UTC)
        for order in orders:
            price = self._last_price.get(order.symbol)
            if price is None:
                raise ValueError(f"no price known for {order.symbol}; call set_price() first")

            existing = self._positions.get(order.symbol)
            existing_qty = existing.qty if existing else 0.0
            new_qty = existing_qty + order.qty

            if existing and existing_qty and order.qty and (existing_qty > 0) == (order.qty > 0):
                # Adding to a position in the same direction: blend the average price.
                new_avg = ((existing_qty * existing.avg_price) + (order.qty * price)) / new_qty
            else:
                new_avg = price if new_qty else 0.0

            self._positions[order.symbol] = Position(symbol=order.symbol, qty=new_qty, avg_price=new_avg)
            self._cash -= order.qty * price
            fills.append(Fill(symbol=order.symbol, qty=order.qty, price=price, ts=now))
        return fills

    def bars(self, symbol: str, lookback_days: int) -> list[Bar]:
        raise NotImplementedError("SimBroker has no market data of its own; feed it via tradebot.data.sources")
