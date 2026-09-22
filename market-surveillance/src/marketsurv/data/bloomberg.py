"""Thin Bloomberg pull layer (Desktop API via xbbg). Requires a logged-in Terminal on this machine.

Everything lands in data/raw/ (git-ignored). Verify field mnemonics with FLDS<GO> on the Terminal;
they differ by asset class and change over time.
"""

from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"


def _blp():
    try:
        from xbbg import blp
    except ImportError as e:  # pragma: no cover
        raise SystemExit("Install the Bloomberg extra: uv sync --extra bloomberg") from e
    return blp


def daily_history(tickers: list[str], start: str, end: str, name: str) -> pd.DataFrame:
    """Daily PX_LAST and PX_VOLUME, adjusted for splits and dividends so returns can be taken
    straight from PX_LAST."""
    df = _blp().bdh(tickers, ["PX_LAST", "PX_VOLUME"], start, end, adjust="all")
    df.to_parquet(RAW / f"{name}.parquet")
    return df


def reference(tickers: list[str], fields: list[str], name: str) -> pd.DataFrame:
    df = _blp().bdp(tickers, fields)
    df.to_parquet(RAW / f"{name}.parquet")
    return df


def intraday_bars(ticker: str, start: str, end: str, interval_min: int = 1) -> pd.DataFrame:
    """TRADE bars. Bloomberg only retains a limited intraday window; pull early and cache."""
    df = _blp().bdib(ticker, start, end, typ="TRADE", interval=interval_min)
    df.to_parquet(RAW / f"bars_{ticker.replace(' ', '_')}_{start[:10]}_{end[:10]}.parquet")
    return df
