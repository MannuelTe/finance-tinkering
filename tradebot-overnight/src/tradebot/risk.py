from __future__ import annotations

from dataclasses import dataclass

from tradebot.broker.base import Order
from tradebot.config import settings


@dataclass(frozen=True)
class RiskCheckResult:
    approved: list[Order]
    rejected: list[tuple[Order, str]]


def check_orders(orders: list[Order], nav: float, last_price: dict[str, float]) -> RiskCheckResult:
    """Pre-trade checks. Runs in-process before every broker.place() call — this is the last
    line of defense before an order reaches IBKR, so it fails closed (reject, don't guess)."""

    if settings.kill_switch:
        return RiskCheckResult(approved=[], rejected=[(o, "kill switch engaged") for o in orders])

    approved: list[Order] = []
    rejected: list[tuple[Order, str]] = []
    for order in orders:
        price = last_price.get(order.symbol)
        if price is None:
            rejected.append((order, "no price available"))
            continue

        notional = abs(order.qty) * price
        if notional > float(settings.max_notional):
            rejected.append(
                (order, f"notional {notional:.2f} exceeds MAX_NOTIONAL={settings.max_notional}")
            )
            continue

        approved.append(order)
    return RiskCheckResult(approved=approved, rejected=rejected)
