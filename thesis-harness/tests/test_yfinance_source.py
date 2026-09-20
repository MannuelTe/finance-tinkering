from __future__ import annotations

import numpy as np
import pandas as pd

from tradebot.data.sources import yfinance as source


def _download(frame: pd.DataFrame):
    def fake(*args, **kwargs):
        return frame

    return fake


def _raw(open_, close) -> pd.DataFrame:
    idx = pd.date_range("2026-09-14", periods=len(close), freq="D", name="Date")
    return pd.DataFrame(
        {"Open": open_, "High": close, "Low": open_, "Close": close, "Volume": 1}, index=idx
    )


def test_trailing_incomplete_bar_is_dropped(monkeypatch):
    raw = _raw([1.0, 2.0, np.nan], [1.5, 2.5, np.nan])  # latest bar still forming
    monkeypatch.setattr(source.yf, "download", _download(raw))
    df = source.fetch_daily_bars("SPY", 30)
    assert len(df) == 2 and df.close.tolist() == [1.5, 2.5]


def test_interior_gap_is_kept_so_callers_can_reject_it(monkeypatch):
    raw = _raw([1.0, np.nan, 3.0], [1.5, np.nan, 3.5])
    monkeypatch.setattr(source.yf, "download", _download(raw))
    df = source.fetch_daily_bars("SPY", 30)
    assert len(df) == 3 and df.close.isna().sum() == 1


def test_lookback_is_calendar_days(monkeypatch):
    seen = {}

    def fake(symbol, **kwargs):
        seen.update(kwargs)
        return _raw([1.0], [1.5])

    monkeypatch.setattr(source.yf, "download", fake)
    source.fetch_daily_bars("SPY", 365)
    assert "start" in seen and "period" not in seen
