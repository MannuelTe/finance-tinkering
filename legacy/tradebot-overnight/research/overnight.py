"""SPY overnight research CLI (port of the archived ibkr_overnight.py). Places NO orders.

Examples:
  uv run python research/overnight.py backtest --source yahoo --symbol SPY --cost-bps 2
  uv run python research/overnight.py signal --source yahoo --symbol SPY
  uv run python research/overnight.py backtest SPY.csv --cost-bps 2
  uv run python research/overnight.py download --symbol SPY --output SPY.csv   # needs the gateway
  uv run python research/overnight.py plan --symbol SPY --quantity 10 --account DU1234567
  uv run python research/overnight.py screen returns.csv quotes.csv

CSV bars: date,open,close (one row EVERY session, ascending). See tradebot/overnight.py for the
model, timing and cost assumptions and for what production use would still require.
"""

from __future__ import annotations

import argparse
import dataclasses
import json

import pandas as pd

from tradebot import overnight
from tradebot.config import settings


def _bars(args: argparse.Namespace) -> pd.DataFrame:
    if args.csv:
        return overnight.load_bars(args.csv)
    if args.source == "yahoo":
        # Yahoo bars are split AND dividend adjusted for open and close together (auto_adjust).
        from tradebot.data.sources.yfinance import fetch_daily_bars

        return overnight.frame_to_bars(fetch_daily_bars(args.symbol, args.days))
    raise SystemExit("give a CSV path, or --source yahoo")


def _config(args: argparse.Namespace) -> overnight.OvernightConfig:
    return overnight.OvernightConfig(
        args.window, args.cost_bps, args.fraction, args.cap, args.z, args.binary
    )


def _add_model_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("csv", nargs="?", help="date,open,close CSV (or use --source)")
    p.add_argument("--source", choices=["yahoo"], help="fetch bars instead of a CSV")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--days", type=int, default=1500, help="calendar days of history for --source")
    p.add_argument("--window", type=int, default=60)
    p.add_argument("--cost-bps", type=float, default=2.0, help="ALL-IN roundtrip cost, not per side")
    p.add_argument("--fraction", type=float, default=0.25)
    p.add_argument("--cap", type=float, default=1.0)
    p.add_argument("--z", type=float, default=0.0)
    p.add_argument("--binary", action="store_true", help="full size or nothing each day")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("backtest")
    _add_model_args(p)
    p.add_argument("--initial", type=float, default=10_000)
    p.add_argument("--output", help="write the per-session table here (refuses to overwrite)")

    _add_model_args(sub.add_parser("signal"))

    p = sub.add_parser("download", help="read-only IBKR daily bars of completed sessions")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--host", default=settings.ib_host)
    p.add_argument("--port", type=int, default=settings.ib_port)
    p.add_argument("--client-id", type=int, default=91)
    p.add_argument("--duration", default="2 Y")
    p.add_argument("--output", required=True)

    p = sub.add_parser("plan", help="print the plan-only MOC entry / OPG exit orders")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--quantity", type=int, required=True)
    p.add_argument("--account", required=True)

    p = sub.add_parser("screen")
    p.add_argument("returns_csv")
    p.add_argument("quotes_csv")
    p.add_argument("--min-beta", type=float, default=1.1)
    p.add_argument("--min-corr", type=float, default=0.8)
    p.add_argument("--min-saving-bps", type=float, default=0.1)

    args = parser.parse_args()

    if args.command == "download":
        from ib_async import IB

        from tradebot.data.sources.ibkr import download_daily_bars

        ib = IB()
        ib.connect(args.host, args.port, clientId=args.client_id, readonly=True)
        try:
            frame = download_daily_bars(ib, args.symbol, args.duration)
        finally:
            ib.disconnect()
        frame.to_csv(args.output, index=False, mode="x")
        print(f"Saved {len(frame)} PRICE-only bars to {args.output}; dividends excluded. No orders submitted.")
    elif args.command == "plan":
        entry, exit_order = overnight.order_plan(args.symbol, args.quantity, args.account)
        print(json.dumps([dataclasses.asdict(entry), dataclasses.asdict(exit_order)], indent=2))
    elif args.command == "screen":
        results = overnight.screen(
            args.returns_csv, args.quotes_csv,
            min_beta=args.min_beta, min_corr=args.min_corr, min_saving=args.min_saving_bps,
        )
        print(json.dumps(results, indent=2, allow_nan=False))
    else:
        bars, config = _bars(args), _config(args)
        if args.command == "signal":
            print(json.dumps(overnight.next_signal(bars, config), indent=2, allow_nan=False))
        else:
            out = overnight.backtest(bars, config, args.initial)
            if args.output:
                out.to_csv(args.output, mode="x")
            print(json.dumps(overnight.summary(out, args.initial), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
