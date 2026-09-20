"""CLI entry point for tradebot.backtest — run a constant-weight strategy over yfinance history.

Usage:
    uv run python research/backtest.py --weights SPY:0.6,TLT:0.4 --lookback-days 730
"""

from __future__ import annotations

import argparse

from tradebot.backtest import run_backtest
from tradebot.instruments import INSTRUMENTS


def _parse_weights(raw: str) -> dict[str, float]:
    weights = {}
    for pair in raw.split(","):
        symbol, weight = pair.split(":")
        weights[symbol.strip()] = float(weight)
    return weights


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest a constant-weight strategy (in the base currency).")
    parser.add_argument("--weights", default="SPY:0.6,TLT:0.4", help="symbol:weight pairs, comma-separated")
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--starting-cash", type=float, default=100_000.0)
    args = parser.parse_args()

    result = run_backtest(
        _parse_weights(args.weights),
        lookback_days=args.lookback_days,
        starting_cash=args.starting_cash,
        instruments=INSTRUMENTS,  # non-base-currency ETFs are converted
    )

    print(f"period:       {result.nav_series.index[0].date()} -> {result.nav_series.index[-1].date()}")
    print(f"total return: {result.total_return:.2%}")
    print(f"CAGR:         {result.cagr:.2%}")
    print(f"max drawdown: {result.max_drawdown:.2%}")
    print(f"sharpe:       {result.sharpe:.2f}")


if __name__ == "__main__":
    main()
