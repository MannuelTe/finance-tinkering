"""PURPOSE: load/cache Yahoo prices and build strictly lagged market-state features.
INPUTS: replication config and optional cache refresh flag.
OUTPUTS: adjusted prices, realized returns, and causal 3N-dimensional features.
"""


import numpy as np
import pandas as pd

from .config import ROOT, ReplicationConfig

CACHE = ROOT / "data" / "prices.csv"


def load_prices(config: ReplicationConfig, refresh: bool = False) -> pd.DataFrame:
    if CACHE.exists() and not refresh:
        prices = pd.read_csv(CACHE, index_col=0, parse_dates=True)
    else:
        import yfinance as yf

        raw = yf.download(
            list(config.tickers), start=config.data_start, end=config.data_end_exclusive,
            auto_adjust=True, progress=False,
        )
        prices = raw.get("Close", raw)
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(config.tickers[0])
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        prices.to_csv(CACHE)
    prices.index = pd.DatetimeIndex(prices.index).tz_localize(None).rename("date")
    return prices.loc[:, list(config.tickers)].sort_index().dropna()


def market_data(
    prices: pd.DataFrame, config: ReplicationConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return simple outcomes and x_t built only from returns observed through t-1."""
    simple = prices.pct_change()
    log_returns = np.log(prices).diff()
    known = log_returns.shift(1)
    vol = known.rolling(config.volatility_window).std(ddof=1)
    momentum = known.rolling(config.momentum_window).mean()
    features = pd.concat(
        [known.add_prefix("ret_"), vol.add_prefix("vol_"), momentum.add_prefix("mom_")], axis=1,
    ).dropna()
    outcomes = simple.reindex(features.index)
    valid = outcomes.notna().all(axis=1)
    return outcomes.loc[valid], features.loc[valid]

