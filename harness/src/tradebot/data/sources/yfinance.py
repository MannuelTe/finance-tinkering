from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf


def fx_rate(currency: str, base: str) -> float:
    """Latest Yahoo spot for `currency` in `base` (e.g. USDCAD=X = CAD per 1 USD)."""
    if currency == base:
        return 1.0
    close = fetch_daily_bars(f"{currency}{base}=X", 10)["close"].dropna()
    if close.empty:
        raise ValueError(f"no Yahoo FX rate for {currency}->{base}")
    return float(close.iloc[-1])


def fetch_daily_bars(symbol: str, lookback_days: int = 365) -> pd.DataFrame:
    """Free, no-auth daily bars for research/backtesting. Not used in the live path — IBKR
    is the execution broker, this is just for building/testing strategies without a Gateway."""
    # `lookback_days` is CALENDAR days, matching the IBKR source. (yfinance's period="Nd" returns
    # N trading sessions, not N calendar days, so the two sources disagreed for the same value.)
    start = (datetime.now(UTC) - timedelta(days=lookback_days)).date().isoformat()
    df = yf.download(symbol, start=start, interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        # Recent yfinance versions return (field, ticker) columns even for a single symbol;
        # collapsing to the field level avoids df["close"] silently returning a DataFrame.
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(
        columns={
            "Date": "ts",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df = df[["ts", "open", "high", "low", "close", "volume"]]
    # Yahoo sometimes returns the latest (still-forming) session with volume but NaN prices.
    # Drop trailing incomplete bars only: an interior NaN is a missing session and must stay
    # visible so callers that need every session can reject it.
    complete = df[["open", "close"]].notna().all(axis=1)
    if complete.any():
        df = df.loc[: complete[complete].index[-1]]
    return df.reset_index(drop=True)
