"""Price data: yfinance with local CSV cache, user CSV files, or deterministic synthetic GBM.

PURPOSE: produce a clean adjusted-close panel for universe + benchmark.
INPUTS: `Thesis` (data_source, universe, benchmark, start, end, csv_files, seed).
OUTPUTS: DataFrame[date x ticker] of adjusted closes, rows with any NaN dropped;
yfinance results cached in theses/<slug>/data/prices.csv (gitignored).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from thesispaper.spec import Thesis


def synthetic_prices(
    tickers: list[str], start: str, end: str | None = None, seed: int = 0,
    mu: float = 0.07, sigma: float = 0.18, n_years: float = 4.0,
) -> pd.DataFrame:
    """Deterministic geometric Brownian motion on business days, one stream per ticker."""
    t0 = pd.Timestamp(start)
    t1 = pd.Timestamp(end) if end else t0 + pd.Timedelta(days=int(365 * n_years))
    idx = pd.bdate_range(t0, t1)
    dt = 1 / 252
    cols = {}
    for i, tk in enumerate(tickers):
        rng = np.random.default_rng([seed, i])
        z = rng.standard_normal(len(idx))
        logret = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
        cols[tk] = 100.0 * np.exp(np.cumsum(logret))
    return pd.DataFrame(cols, index=idx).rename_axis("date")


def _tickers(spec: Thesis) -> list[str]:
    return list(dict.fromkeys([*spec.universe, spec.benchmark]))


def _download(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    close = raw.get("Close", raw)
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close


def _read_csv(spec: Thesis) -> pd.DataFrame:
    cols = {}
    for tk, rel in spec.csv_files.items():
        df = pd.read_csv(spec.directory / rel, index_col=0, parse_dates=True)
        col = next((c for c in ("Adj Close", "adj_close", "Close", "close") if c in df), None)
        cols[tk] = df[col] if col else df.iloc[:, 0]
    return pd.DataFrame(cols)


def _clean(df: pd.DataFrame, spec: Thesis) -> pd.DataFrame:
    df = df[_tickers(spec)].sort_index()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None).rename("date")
    df = df.loc[df.index >= pd.Timestamp(spec.start)]
    if spec.end:
        df = df.loc[df.index <= pd.Timestamp(spec.end)]
    df = df.dropna(how="any")
    if len(df) < 3:
        raise ValueError(f"fewer than 3 usable price rows for {spec.slug}")
    return df


def load_prices(spec: Thesis, refresh: bool = False) -> pd.DataFrame:
    """Load adjusted closes for universe + benchmark according to spec.data_source."""
    tickers = _tickers(spec)
    if spec.data_source == "synthetic":
        return _clean(synthetic_prices(tickers, spec.start, spec.end, spec.seed), spec)
    if spec.data_source == "csv":
        return _clean(_read_csv(spec), spec)
    cache = spec.directory / "data" / "prices.csv"
    if cache.exists() and not refresh:
        cached = pd.read_csv(cache, index_col=0, parse_dates=True)
        if set(tickers) <= set(cached.columns):
            return _clean(cached, spec)
    df = _download(tickers, spec.start, spec.end)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache)
    return _clean(df, spec)
