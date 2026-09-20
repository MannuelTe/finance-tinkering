from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from ib_async import IB

from tradebot.broker.ibkr import contract_for


def fetch_daily_bars(ib: IB, symbol: str, lookback_days: int = 365) -> pd.DataFrame:
    """Pull daily bars for research/backtesting. Takes an already-connected IB instance so
    callers can share one connection across many symbols instead of reconnecting per call."""
    contract = contract_for(symbol)
    raw = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=f"{lookback_days} D",
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
    )
    return pd.DataFrame(
        {
            "ts": [
                b.date if isinstance(b.date, datetime) else datetime.combine(b.date, datetime.min.time())
                for b in raw
            ],
            "open": [b.open for b in raw],
            "high": [b.high for b in raw],
            "low": [b.low for b in raw],
            "close": [b.close for b in raw],
            "volume": [b.volume for b in raw],
        }
    )


def download_daily_bars(ib: IB, symbol: str, duration: str = "2 Y", now: datetime | None = None) -> pd.DataFrame:
    """Read-only sequential historical request of COMPLETED sessions: date, open, close.

    The request ends at today's midnight UTC so a partial current-session bar can never be
    included (US sessions close at 20:00-21:00 UTC). `duration` is IBKR syntax ("2 Y", "6 M"):
    daily requests over a year must use years. TRADES bars are a PRICE-return dataset (splits
    adjusted, dividends not), so total-return research needs a separate adjusted source.
    """
    end = (now or datetime.now(UTC)).strftime("%Y%m%d-00:00:00")
    raw = ib.reqHistoricalData(
        contract_for(symbol),
        endDateTime=end,
        durationStr=duration,
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
    )
    if not raw:
        raise RuntimeError(f"No historical bars returned for {symbol} (permissions, symbol, or duration?)")
    return pd.DataFrame(
        {
            "date": [pd.Timestamp(b.date).strftime("%Y-%m-%d") for b in raw],
            "open": [b.open for b in raw],
            "close": [b.close for b in raw],
        }
    )


INTRADAY_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


def fetch_intraday_bars(
    ib: IB,
    symbol: str,
    duration: str,
    end: datetime | None = None,
    bar_size: str = "5 mins",
) -> pd.DataFrame:
    """One read-only request of regular-hours intraday bars. `ts` is the bar START, UTC-aware.

    `end=None` means "now" (the last bar may still be forming: callers must only use bars that
    completed before their decision instant). Otherwise it is an absolute UTC instant.
    """
    raw = ib.reqHistoricalData(
        contract_for(symbol),
        endDateTime="" if end is None else end.astimezone(UTC).strftime("%Y%m%d-%H:%M:%S"),
        durationStr=duration,
        barSizeSetting=bar_size,
        whatToShow="TRADES",
        useRTH=True,
        formatDate=2,
    )
    return pd.DataFrame(
        {
            "ts": [pd.Timestamp(b.date).tz_convert("UTC") for b in raw],
            "open": [b.open for b in raw],
            "high": [b.high for b in raw],
            "low": [b.low for b in raw],
            "close": [b.close for b in raw],
            "volume": [b.volume for b in raw],
        },
        columns=INTRADAY_COLUMNS,
    )


def download_intraday_history(
    ib: IB,
    symbol: str,
    months: int,
    bar_size: str = "5 mins",
    end: datetime | None = None,
    on_chunk=None,
) -> pd.DataFrame:
    """Page backwards one month per request (IBKR's limit for 5-minute bars) until `months`
    months are covered or the data runs out. Chunks overlap harmlessly and are de-duplicated."""
    chunks: list[pd.DataFrame] = []
    cursor = end
    for i in range(months):
        chunk = fetch_intraday_bars(ib, symbol, "1 M", cursor, bar_size)
        if chunk.empty:
            break
        chunks.append(chunk)
        if on_chunk:
            on_chunk(i + 1, months, chunk)
        cursor = chunk["ts"].min().to_pydatetime()
    if not chunks:
        raise RuntimeError(f"No intraday bars returned for {symbol}")
    return (
        pd.concat(chunks)
        .drop_duplicates(subset="ts")
        .sort_values("ts")
        .reset_index(drop=True)
    )
