"""Periodic rebalancing runner.

PURPOSE: each cycle, size orders toward the target weights, gate them through risk checks, place
         them at the broker and persist NAV/orders/fills.
INPUTS:  a Broker, a Strategy, optional DB session factory, settings (TARGET_WEIGHTS etc.).
OUTPUTS: orders at the broker and rows in the state DB; `main()` is the CLI/loop entry point.
"""

from __future__ import annotations

import argparse
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tradebot.broker.base import Broker, Order
from tradebot.broker.ibkr import IBKRBroker
from tradebot.config import settings
from tradebot.execution.sizer import size_orders
from tradebot.instruments import INSTRUMENTS
from tradebot.notify import notify
from tradebot.portfolio import parse_weights, validate_weights
from tradebot.risk import check_orders
from tradebot.state.persistence import record_nav, record_orders_and_fills
from tradebot.state.reconcile import reconcile
from tradebot.strategy.base import StrategyContext
from tradebot.strategy.constant import ConstantWeightStrategy

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]

def target_weights() -> dict[str, float]:
    """Target weights from settings.target_weights ("SYM:0.6,SYM2:0.4")."""
    weights = validate_weights(parse_weights(settings.target_weights))
    if not weights:
        raise SystemExit("TARGET_WEIGHTS is empty; set it, e.g. TARGET_WEIGHTS=SPY:0.6,TLT:0.4")
    return weights


def build_strategy() -> ConstantWeightStrategy:
    return ConstantWeightStrategy(weights=target_weights())


def prices_in_base(broker: Broker, symbols: set[str]) -> dict[str, float]:
    """Latest price per symbol converted into settings.base_currency. Sizing divides a
    base-currency notional by price, so mixing native prices (USD, CAD, EUR) in here would
    silently mis-size every non-base ETF. Symbols we can't price (unregistered, e.g. an
    unrelated holding in the account, or no market data) are omitted and therefore untouched."""
    base = settings.base_currency
    fx: dict[str, float] = {}
    prices: dict[str, float] = {}
    for symbol in sorted(symbols):
        inst = INSTRUMENTS.get(symbol)
        if inst is None:
            logger.warning("no instrument definition for %s; leaving it alone", symbol)
            continue
        native = broker.price(symbol)
        if native is None or not math.isfinite(native) or native <= 0:
            logger.warning("no usable price for %s (%s); skipping it this cycle", symbol, native)
            continue
        if inst.currency not in fx:
            fx[inst.currency] = broker.fx_rate(inst.currency, base)
        rate = fx[inst.currency]
        if not math.isfinite(rate) or rate <= 0:
            logger.warning("no usable %s->%s FX rate (%s); skipping %s", inst.currency, base, rate, symbol)
            continue
        prices[symbol] = native * rate
    return prices


def _drop_orders_already_working(broker: Broker, orders: list[Order]) -> list[Order]:
    """Positions only change when an order fills, so an order that is still working (slow fill,
    exchange closed) would be sized again from the same stale positions on the next cycle and
    stacked on top of itself. Skip any symbol that already has a working order."""
    if not orders:
        return orders
    working = broker.open_order_symbols()
    kept: list[Order] = []
    for order in orders:
        if order.symbol in working:
            logger.info("skipping %s: an order is already working at the broker", order.symbol)
        else:
            kept.append(order)
    return kept


def _drop_orders_for_closed_markets(broker: Broker, orders: list[Order]) -> list[Order]:
    """Only trade a symbol while its own exchange is in its regular session. Otherwise market
    orders either queue and fill at the next open at a price we never saw (Xetra, London, US)
    or get cancelled outright (Toronto), and the bot would retry every cycle all night."""
    kept: list[Order] = []
    for order in orders:
        if broker.is_market_open(order.symbol):
            kept.append(order)
        else:
            logger.info("skipping %s: its market is closed", order.symbol)
    return kept


def run_once(
    broker: Broker,
    strategy: ConstantWeightStrategy,
    session_factory: SessionFactory | None = None,
) -> None:
    if not broker.is_connected():
        # Gateway is down (daily restart / pending 2FA push). Do nothing and retry next
        # tick rather than guessing at positions or NAV — see docker-compose notes.
        logger.warning("broker not connected; skipping this cycle")
        return

    nav = broker.nav()
    _persist(session_factory, lambda s: record_nav(s, nav))
    positions = broker.positions()
    ctx = StrategyContext(positions=positions, nav=nav)
    weights = strategy.target_weights(datetime.now(UTC), ctx)

    last_price = prices_in_base(broker, set(weights) | {p.symbol for p in positions})
    orders = size_orders(weights, positions, nav, last_price, whole_shares=True)
    orders = _drop_orders_for_closed_markets(broker, orders)
    orders = _drop_orders_already_working(broker, orders)
    result = check_orders(orders, nav, last_price)

    for order, reason in result.rejected:
        logger.warning("order rejected: %s (%s)", order, reason)
        notify(f"Order rejected: {order.symbol} qty={order.qty} — {reason}")

    if result.approved:
        fills = broker.place(result.approved)
        for fill in fills:
            logger.info("filled: %s", fill)
        _persist(session_factory, lambda s: record_orders_and_fills(s, result.approved, fills))
        notify(f"Placed {len(result.approved)} order(s), {len(fills)} fill(s)")


def _persist(session_factory: SessionFactory | None, write: Callable[[Session], None]) -> None:
    """Best-effort DB write. Orders may already have been placed by the time this runs, so a
    DB failure is logged loudly but never allowed to abort the cycle."""
    if session_factory is None:
        return
    try:
        with session_factory() as session:
            write(session)
    except Exception:
        logger.exception("failed to persist run state")


def main(once: bool = False) -> None:
    logging.basicConfig(level=logging.INFO)
    broker = IBKRBroker()
    broker.connect()
    strategy = build_strategy()
    broker.check_setup(target_weights())  # fail fast on a wrong currency / unresolved ETF
    reconcile(broker)
    session_factory = sessionmaker(create_engine(settings.database_url))

    if once:
        # One controlled cycle; errors propagate so a failure is loud, not swallowed.
        run_once(broker, strategy, session_factory)
        return

    while True:
        try:
            run_once(broker, strategy, session_factory)
        except Exception:
            logger.exception("run_once failed")
            notify("tradebot: run_once failed, see logs")
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="tradebot runner")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    main(once=parser.parse_args().once)
