"""Target weights to whole-share orders.

PURPOSE: Target weights to whole-share orders.
INPUTS:  target weights, positions, NAV, base-currency prices.
OUTPUTS: list of Orders that move holdings toward the targets.
"""

from __future__ import annotations

import math

from tradebot.broker.base import Order, Position


def size_orders(
    target_weights: dict[str, float],
    positions: list[Position],
    nav: float,
    last_price: dict[str, float],
    min_trade_notional: float = 1.0,
    whole_shares: bool = False,
) -> list[Order]:
    """Turn target weights + current positions + NAV into the order list that closes the gap.

    `last_price` and `nav` must be in the same currency (the base currency); convert native
    prices first. With `whole_shares`, quantities are truncated toward zero (never overspend),
    as required for exchange-listed ETFs; leave it off for fractional backtests.

    Symbols with no known price are silently skipped (nothing to size against); callers
    should have already tried to backfill a price via broker.bars() before calling this.
    """
    current_qty = {p.symbol: p.qty for p in positions}
    symbols = set(target_weights) | set(current_qty)

    orders: list[Order] = []
    for symbol in symbols:
        price = last_price.get(symbol)
        if price is None or not math.isfinite(price) or price <= 0:
            continue

        target_notional = target_weights.get(symbol, 0.0) * nav
        target_qty = target_notional / price
        delta_qty = target_qty - current_qty.get(symbol, 0.0)
        if whole_shares:
            delta_qty = float(math.trunc(delta_qty))

        if delta_qty == 0 or abs(delta_qty * price) < min_trade_notional:
            continue

        orders.append(Order(symbol=symbol, qty=delta_qty))
    return orders
