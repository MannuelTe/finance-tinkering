"""Show the orders the bot would place for the target portfolio, without any broker.

Uses the runner's own pricing/FX conversion, sizer and risk gate, fed by Yahoo quotes and an
assumed starting NAV (flat account, no existing positions). Nothing is sent anywhere.

Usage:
    uv run python research/dry_run.py --nav 10000
"""

from __future__ import annotations

import argparse

from tradebot.broker.base import Bar, Fill, Order, Position
from tradebot.config import settings
from tradebot.data.sources.yfinance import fetch_daily_bars
from tradebot.data.sources.yfinance import fx_rate as yahoo_fx_rate
from tradebot.execution.runner import prices_in_base
from tradebot.execution.sizer import size_orders
from tradebot.instruments import INSTRUMENTS
from tradebot.portfolio import blended_weights
from tradebot.risk import check_orders


class YahooQuoteBroker:
    """Read-only Broker stand-in: latest Yahoo close per symbol, Yahoo FX, flat account."""

    def __init__(self, nav: float) -> None:
        self._nav = nav

    def is_connected(self) -> bool:
        return True

    def nav(self) -> float:
        return self._nav

    def positions(self) -> list[Position]:
        return []

    def price(self, symbol: str) -> float | None:
        close = fetch_daily_bars(INSTRUMENTS[symbol].yahoo_symbol, 10)["close"].dropna()
        return float(close.iloc[-1]) if len(close) else None

    def fx_rate(self, currency: str, base: str) -> float:
        return yahoo_fx_rate(currency, base)

    def bars(self, symbol: str, lookback_days: int) -> list[Bar]:
        return []

    def place(self, orders: list[Order]) -> list[Fill]:
        raise RuntimeError("dry run never places orders")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run the target portfolio.")
    parser.add_argument("--nav", type=float, default=10_000.0, help=f"assumed NAV in {settings.base_currency}")
    args = parser.parse_args()

    weights = blended_weights()
    broker = YahooQuoteBroker(args.nav)
    base = settings.base_currency
    prices = prices_in_base(broker, set(weights))
    orders = size_orders(weights, [], args.nav, prices, whole_shares=True)

    cap = settings.max_notional
    live = check_orders(orders, args.nav, prices)  # with the configured per-order cap
    rejected_by_cap = {o.symbol for o, _ in live.rejected}

    print(f"\nNAV {args.nav:,.0f} {base}; per-order cap MAX_NOTIONAL={cap} {base}\n")
    print(f"{'symbol':7} {'ccy':4} {'target':>7} {'price ' + base:>11} {'qty':>5} {'order ' + base:>11} {'actual':>7}  cap check")
    invested = 0.0
    for order in sorted(orders, key=lambda o: -o.qty * prices[o.symbol]):
        px = prices[order.symbol]
        notional = order.qty * px
        invested += notional
        status = f"REJECTED (> {cap})" if order.symbol in rejected_by_cap else "ok"
        print(
            f"{order.symbol:7} {INSTRUMENTS[order.symbol].currency:4} {weights[order.symbol]:>7.1%} "
            f"{px:>11,.2f} {order.qty:>5.0f} {notional:>11,.2f} {notional / args.nav:>7.1%}  {status}"
        )
    skipped = set(weights) - {o.symbol for o in orders}
    for symbol in sorted(skipped):
        print(f"{symbol:7} no order (price missing, or under one share / 1.0 {base})")
    print(f"\ninvested {invested:,.2f} {base} ({invested / args.nav:.1%} of NAV); cash left {args.nav - invested:,.2f}")
    print(f"orders passing the cap: {len(live.approved)} of {len(orders)}")


if __name__ == "__main__":
    main()
