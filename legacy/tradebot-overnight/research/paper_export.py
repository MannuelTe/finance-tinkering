"""Export the data behind the volatility-aware overnight paper as plain CSVs.

Writes to graphics_paper/data/ (read by graphics_paper/render.py, which needs only pandas and
matplotlib). Needs the IBKR paper gateway up for the intraday history (read-only, cached):

    uv run python research/paper_export.py --months 36
    uv run python research/paper_export.py --months 36 --no-ibkr     # reuse the cache only

Strategy, accounting and caveats: see the docstring of tradebot/paper.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from tradebot import overnight, paper
from tradebot.backtest import run_backtest
from tradebot.config import settings
from tradebot.data.sources.yfinance import fetch_daily_bars
from tradebot.instruments import INSTRUMENTS
from tradebot.portfolio import CLASSIC, SLEEVE_LONG, blended_weights

OUT = Path(__file__).resolve().parent.parent / "graphics_paper" / "data"


def load_intraday(months: int, use_ibkr: bool, cache: Path) -> pd.DataFrame:
    """5-minute SPY bars (regular hours). Cached; a run tops the cache up with the latest month."""
    have = pd.read_csv(cache, parse_dates=["ts"]) if cache.exists() else None
    if have is not None:
        have["ts"] = pd.to_datetime(have["ts"], utc=True)
    if not use_ibkr:
        if have is None:
            sys.exit(f"no cache at {cache}; run once with the gateway up")
        return have

    from ib_async import IB

    from tradebot.data.sources.ibkr import download_intraday_history

    ib = IB()
    ib.connect(settings.ib_host, settings.ib_port, clientId=settings.ib_client_id + 20, readonly=True)
    try:
        wanted = 2 if have is not None else months  # cache present: just refresh the tail
        fresh = download_intraday_history(
            ib, "SPY", wanted,
            on_chunk=lambda i, n, c: print(f"  intraday chunk {i}/{n}: {len(c)} bars from {c.ts.min():%Y-%m-%d}", flush=True),
        )
    finally:
        ib.disconnect()
    merged = fresh if have is None else pd.concat([have, fresh])
    merged = merged.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(cache, index=False)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument("--cost-bps", type=float, default=2.0, help="ALL-IN roundtrip cost")
    parser.add_argument("--min-weight", type=float, default=0.5)
    parser.add_argument("--window", type=int, default=60)
    parser.add_argument("--no-ibkr", action="store_true", help="use the cached intraday bars only")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print("intraday bars ...")
    bars = load_intraday(args.months, not args.no_ibkr, args.out / "cache" / "spy_5min.csv")
    first_day = bars["ts"].min().normalize()
    print(f"  {len(bars)} bars, {first_day:%Y-%m-%d} .. {bars['ts'].max():%Y-%m-%d}")
    intraday = overnight.intraday_variance_by_day(bars)
    print(f"  {len(intraday)} sessions with a usable 15:00 volatility reading")

    # Daily history reaches back before the first intraday day so the model has its warm-up.
    span = (pd.Timestamp.now(tz="UTC").normalize() - first_day).days + int(args.window * 1.6) + 10
    print(f"daily bars and portfolio legs ({span} calendar days) ...")
    daily = overnight.frame_to_bars(fetch_daily_bars("SPY", span))
    weights = blended_weights(SLEEVE_LONG)
    spy_weight = weights["SPY"]
    rest = {s: w for s, w in weights.items() if s != "SPY"}

    def nav(w: dict[str, float]) -> pd.Series:
        return run_backtest(
            w, lookback_days=span, instruments=INSTRUMENTS, base_currency=settings.base_currency
        ).nav_series

    tables = paper.build_tables(
        daily,
        intraday,
        rest_nav=nav(rest),
        baseline_navs={"blend_hold": nav(weights), "classic": nav(CLASSIC), "spy": nav({"SPY": 1.0})},
        spy_weight=spy_weight,
        cost_bps=args.cost_bps,
        min_weight=args.min_weight,
        window=args.window,
    )
    for name, frame in tables.items():
        frame.to_csv(args.out / f"{name}.csv", index=False)
        print(f"  wrote {name}.csv ({len(frame)} rows)")
    vol = intraday[["intraday_var"]].assign(intraday_sigma=lambda f: f["intraday_var"] ** 0.5)
    vol.index.name = "date"
    vol.reset_index().to_csv(args.out / "intraday_vol.csv", index=False)

    meta = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "base_currency": settings.base_currency,
        "portfolio_weights": {k: round(v, 6) for k, v in weights.items()},
        "spy_slice_weight": spy_weight,
        "sleeve_variant": "long history (Europe equal-weight folded into Europe cap-weight)",
        "decision_time": "60 minutes before the close (15:00 ET on a normal day)",
        "intraday": "IBKR TRADES, 5-minute bars, regular trading hours",
        "daily_spy": "Yahoo, split and dividend adjusted open/close",
        "cost_bps_roundtrip": args.cost_bps,
        "min_weight": args.min_weight,
        "model_window": args.window,
        "caveats": [
            "The SPY overnight leg is computed in USD; FX moves during the hold are ignored.",
            "Costs exclude tax, cash interest, commission minimums and volume impact.",
            "The 0.5 min_weight threshold was chosen by the author, not fitted; see the sensitivity data.",
            "History is short (a few years); nothing here is statistically conclusive.",
            "Daily rebalancing to target weights is assumed for the non-SPY holdings.",
        ],
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2))
    print("done ->", args.out)


if __name__ == "__main__":
    main()
