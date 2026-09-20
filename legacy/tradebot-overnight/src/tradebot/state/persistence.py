from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from tradebot.broker.base import Fill, Order
from tradebot.state.models import FillRecord, NavSnapshot, OrderRecord


def record_nav(session: Session, nav: float, taken_at: datetime | None = None) -> None:
    snapshot = NavSnapshot(nav=nav)
    if taken_at is not None:
        snapshot.taken_at = taken_at
    session.add(snapshot)
    session.commit()


def record_orders_and_fills(
    session: Session, orders: Sequence[Order], fills: Sequence[Fill]
) -> None:
    """Persist submitted orders and attach fills to them by symbol. The sizer emits at most one
    order per symbol per cycle, so symbol is enough to match a fill to its order. An order with
    no matching fill stays "submitted"."""
    fills_by_symbol: dict[str, list[Fill]] = {}
    for fill in fills:
        fills_by_symbol.setdefault(fill.symbol, []).append(fill)

    for order in orders:
        matched = fills_by_symbol.get(order.symbol, [])
        record = OrderRecord(
            symbol=order.symbol,
            qty=order.qty,
            order_type=order.order_type,
            status="filled" if matched else "submitted",
        )
        for fill in matched:
            record.fills.append(
                FillRecord(symbol=fill.symbol, qty=fill.qty, price=fill.price, filled_at=fill.ts)
            )
        session.add(record)

    session.commit()
