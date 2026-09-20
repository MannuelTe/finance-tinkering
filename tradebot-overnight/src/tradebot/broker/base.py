from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    avg_price: float


@dataclass(frozen=True)
class Session:
    """One regular trading session of an exchange, as timezone-aware instants."""

    start: datetime
    end: datetime

    @property
    def local_date(self):
        return self.start.date()


@dataclass(frozen=True)
class Order:
    symbol: str
    qty: float  # positive = buy, negative = sell
    order_type: str = "MKT"  # MKT, LMT, or MOC (market-on-close)
    limit_price: float | None = None
    tif: str = "DAY"  # DAY, or OPG for the opening auction
    # transmit=False marks a plan-only order for a supervising system to review. Brokers refuse
    # to place it: a plan must never reach an exchange by accident.
    transmit: bool = True
    account: str | None = None
    ref: str | None = None


@dataclass(frozen=True)
class Fill:
    symbol: str
    qty: float
    price: float
    ts: datetime


@dataclass(frozen=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Broker(Protocol):
    """Implemented by both sim.py and ibkr.py so execution code never branches on which one it has."""

    def is_connected(self) -> bool: ...
    def nav(self) -> float: ...
    def positions(self) -> list[Position]: ...
    def place(self, orders: list[Order]) -> list[Fill]: ...
    def bars(self, symbol: str, lookback_days: int) -> list[Bar]: ...
    def is_market_open(self, symbol: str) -> bool:
        """Whether the instrument's exchange is in its regular session right now. Unknown
        means closed: the runner must not place orders it can't be sure will execute now."""
        ...

    def price(self, symbol: str) -> float | None:
        """Latest price in the instrument's own currency, or None if unavailable."""
        ...

    def open_order_symbols(self) -> set[str]:
        """Symbols that already have a working (not filled/cancelled) order at the broker,
        including orders placed by other clients or by hand. Raise rather than guess: the
        runner must never place an order without knowing this."""
        ...

    def fx_rate(self, currency: str, base: str) -> float:
        """Units of `base` per 1 unit of `currency` (1.0 when they are the same)."""
        ...
