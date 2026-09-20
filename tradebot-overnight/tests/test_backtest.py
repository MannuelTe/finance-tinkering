from __future__ import annotations

import pandas as pd
import pytest

from tradebot.backtest import run_backtest
from tradebot.instruments import Instrument


def _flat_bars(symbol: str, lookback_days: int) -> pd.DataFrame:
    """Constant $100 price, 10 trading days — NAV should be unchanged, no drawdown."""
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    return pd.DataFrame({"ts": dates, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 0})


def _rising_bars(symbol: str, lookback_days: int) -> pd.DataFrame:
    """Price doubles linearly over 10 days."""
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "ts": dates,
            "open": [100.0 + 10 * i for i in range(10)],
            "high": [100.0 + 10 * i for i in range(10)],
            "low": [100.0 + 10 * i for i in range(10)],
            "close": [100.0 + 10 * i for i in range(10)],
            "volume": 0,
        }
    )


def test_flat_prices_preserve_nav():
    result = run_backtest({"SPY": 0.6, "TLT": 0.4}, starting_cash=100_000.0, fetch_bars=_flat_bars)

    assert result.total_return == 0.0
    assert result.max_drawdown == 0.0
    assert result.nav_series.iloc[-1] == 100_000.0


def test_rising_prices_produce_positive_return():
    result = run_backtest({"SPY": 1.0}, starting_cash=100_000.0, fetch_bars=_rising_bars)

    assert result.total_return > 0.0
    assert result.nav_series.iloc[-1] > result.nav_series.iloc[0]


def test_nav_series_indexed_by_date():
    result = run_backtest({"SPY": 0.6, "TLT": 0.4}, starting_cash=100_000.0, fetch_bars=_flat_bars)

    assert len(result.nav_series) == 10
    assert result.nav_series.index[0] == pd.Timestamp("2026-01-01")


def test_foreign_currency_prices_are_converted_to_base():
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])

    def fetch(symbol: str, lookback_days: int) -> pd.DataFrame:
        close = {"AAA": [100.0, 110.0], "EURUSD=X": [2.0, 1.0]}[symbol]
        return pd.DataFrame(
            {"ts": dates, "open": close, "high": close, "low": close, "close": close, "volume": 0}
        )

    result = run_backtest(
        {"AAA": 1.0},
        fetch_bars=fetch,
        instruments={"AAA": Instrument("AAA", "USD")},
        base_currency="EUR",
    )
    # 100 USD @ 2.0 = 50 EUR, then 110 USD @ 1.0 = 110 EUR: +120% in EUR, not +10%.
    assert result.total_return == pytest.approx(1.2, rel=1e-3)
