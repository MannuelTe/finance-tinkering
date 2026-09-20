"""Create a non-transmitting IBKR plan for the metals-hedged frontier thesis."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
THESIS = ROOT / "theses" / "metals_hedged_frontier"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(THESIS))

from strategy import ASSETS, MetalsHedgedFrontier

from thesispaper.data import load_prices
from thesispaper.spec import load_spec
from tradebot.broker.base import Position
from tradebot.broker.ibkr import IBKRBroker
from tradebot.config import settings
from tradebot.execution.sizer import size_orders
from tradebot.instruments import INSTRUMENTS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connect-paper", action="store_true")
    parser.add_argument("--nav", type=float, default=100_000.0,
                        help="offline USD model NAV (default: 100000)")
    for symbol in ASSETS:
        parser.add_argument(f"--{symbol.lower()}-shares", type=float, default=0.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = load_spec("metals_hedged_frontier", ROOT)
    prices = load_prices(spec)
    target = MetalsHedgedFrontier(spec.strategy_params).weights(prices[ASSETS]).to_dict()
    broker = None
    if args.connect_paper:
        if settings.ib_mode != "paper":
            raise RuntimeError("refusing IBKR connection because IB_MODE is not paper")
        broker = IBKRBroker(client_id=settings.ib_client_id + 21)
        broker.connect()
        broker.check_setup(target)
        nav, positions = broker.nav(), broker.positions()
        last_price = {}
        for symbol in ASSETS:
            native = broker.price(symbol)
            if native is None:
                raise RuntimeError(f"no IBKR price for {symbol}")
            last_price[symbol] = native * broker.fx_rate(
                INSTRUMENTS[symbol].currency, settings.base_currency)
    else:
        nav = args.nav
        positions = [Position(symbol, getattr(args, f"{symbol.lower()}_shares"), 0.0)
                     for symbol in ASSETS]
        last_price = {symbol: float(prices[symbol].iloc[-1]) for symbol in ASSETS}
    raw = size_orders(target, positions, nav, last_price, whole_shares=True)
    account = broker.account() if broker else None
    orders = [replace(order, transmit=False, account=account,
                      ref=f"metals-frontier-{prices.index[-1].date()}") for order in raw]
    rows = [{"as_of": str(prices.index[-1].date()), "symbol": order.symbol,
             "side": "BUY" if order.qty > 0 else "SELL", "quantity": abs(order.qty),
             "reference_price_base": last_price[order.symbol],
             "target_weight": target[order.symbol], "transmit": order.transmit,
             "account": "paper" if broker else "offline-model"} for order in orders]
    path = THESIS / "ibkr_order_plan.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    if broker:
        broker.disconnect()
    print(f"wrote {path} with {len(rows)} plan-only order(s); no orders transmitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
