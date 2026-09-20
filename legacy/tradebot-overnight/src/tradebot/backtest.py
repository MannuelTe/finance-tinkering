from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from tradebot.broker.sim import SimBroker
from tradebot.data.sources.yfinance import fetch_daily_bars
from tradebot.execution.sizer import size_orders
from tradebot.instruments import Instrument
from tradebot.strategy.base import StrategyContext
from tradebot.strategy.constant import ConstantWeightStrategy

FetchBars = Callable[[str, int], pd.DataFrame]


@dataclass(frozen=True)
class BacktestResult:
    nav_series: pd.Series
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float


def _to_base_currency(
    df: pd.DataFrame, currency: str, base_currency: str, fetch_bars: FetchBars, lookback_days: int
) -> pd.DataFrame:
    """Convert OHLC from `currency` into `base_currency` using the Yahoo pair
    f"{base}{currency}=X" (units of `currency` per 1 base, e.g. EURUSD=X ~ 1.15). Rates are
    forward-filled onto the asset's own trading dates so calendar mismatches don't drop bars."""
    rates = fetch_bars(f"{base_currency}{currency}=X", lookback_days)
    rate = rates.set_index("ts")["close"].sort_index()
    aligned = rate.reindex(df["ts"], method="ffill").to_numpy()
    out = df.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = out[col].to_numpy() / aligned
    return out.dropna(subset=["close"])


def run_backtest(
    weights: dict[str, float],
    lookback_days: int = 365,
    starting_cash: float = 100_000.0,
    fetch_bars: FetchBars = fetch_daily_bars,
    instruments: Mapping[str, Instrument] | None = None,
    base_currency: str = "EUR",
) -> BacktestResult:
    """Daily-rebalance backtest of a constant-weight strategy over historical daily bars.

    Deliberately skips risk.check_orders(): MAX_NOTIONAL models live per-order capital
    limits, not strategy quality, and would reject nearly every order sized against a
    six-figure backtest NAV. No slippage or commissions either — this validates strategy
    *logic*, not fill realism.

    `instruments` maps symbol -> Instrument (Yahoo ticker + quote currency). Series quoted in a
    currency other than `base_currency` are converted, so mixed-currency portfolios aren't
    valued as if 1 USD == 1 EUR. Symbols without an entry are fetched as-is and assumed to be
    in the base currency.
    """
    strategy = ConstantWeightStrategy(weights=weights)
    instruments = instruments or {}
    bars: dict[str, pd.DataFrame] = {}
    for symbol in weights:
        inst = instruments.get(symbol)
        df = fetch_bars(inst.yahoo_symbol if inst else symbol, lookback_days)
        if inst and inst.currency != base_currency:
            df = _to_base_currency(df, inst.currency, base_currency, fetch_bars, lookback_days)
        bars[symbol] = df

    common_dates: set | None = None
    for df in bars.values():
        dates = set(df["ts"])
        common_dates = dates if common_dates is None else common_dates & dates
    if not common_dates:
        raise ValueError("no overlapping trading dates across symbols")
    dates = sorted(common_dates)

    price_by_date = {symbol: dict(zip(df["ts"], df["close"], strict=True)) for symbol, df in bars.items()}

    broker = SimBroker(starting_cash=starting_cash)
    nav_index: list[datetime] = []
    nav_values: list[float] = []

    for date in dates:
        last_price = {symbol: price_by_date[symbol][date] for symbol in weights}
        for symbol, price in last_price.items():
            broker.set_price(symbol, price)

        ctx = StrategyContext(positions=broker.positions(), nav=broker.nav())
        target_weights = strategy.target_weights(date, ctx)
        orders = size_orders(target_weights, broker.positions(), broker.nav(), last_price)
        if orders:
            broker.place(orders)

        nav_index.append(date)
        nav_values.append(broker.nav())

    nav_series = pd.Series(nav_values, index=pd.Index(nav_index, name="ts"), name="nav")
    return BacktestResult(nav_series=nav_series, **_metrics(nav_series))


def _metrics(nav_series: pd.Series) -> dict[str, float]:
    returns = nav_series.pct_change().dropna()
    total_return = nav_series.iloc[-1] / nav_series.iloc[0] - 1
    years = (nav_series.index[-1] - nav_series.index[0]).days / 365.25
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else float("nan")
    drawdown = nav_series / nav_series.cummax() - 1
    sharpe = (returns.mean() / returns.std()) * (252**0.5) if returns.std() else float("nan")
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": drawdown.min(),
        "sharpe": sharpe,
    }
