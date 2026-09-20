"""Blended portfolio in the base currency (CAD): 50% Europe-heavy sleeve + 50% classic 60/40, with 5% of the whole
moved into EUR-hedged share classes. Weights come from tradebot.portfolio, the same source the
live runner trades.

Usage:
    uv run python research/blended_backtest.py
"""

from __future__ import annotations

import pandas as pd

from tradebot.backtest import _metrics, run_backtest
from tradebot.config import settings
from tradebot.instruments import INSTRUMENTS
from tradebot.portfolio import CLASSIC, SLEEVE, SLEEVE_LONG, blended_weights

LOOKBACK_DAYS = 3000

def run(weights: dict[str, float]) -> pd.Series:
    return run_backtest(
        weights, lookback_days=LOOKBACK_DAYS, instruments=INSTRUMENTS,
        base_currency=settings.base_currency,
    ).nav_series


def report(title: str, runs: dict[str, dict[str, float]]) -> None:
    """Each run's own window is clipped to the youngest ETF in it, so runs differ in length.
    Constant-weight, daily-rebalanced NAV paths don't depend on the start date, so slicing every
    series to the shared window gives an exact like-for-like comparison."""
    navs = {name: run(w) for name, w in runs.items()}
    start = max(n.index[0] for n in navs.values())
    end = min(n.index[-1] for n in navs.values())
    rows = {}
    for name, nav in navs.items():
        m = _metrics(nav.loc[start:end])
        rows[name] = {
            "total return": f"{m['total_return']:.1%}",
            "CAGR": f"{m['cagr']:.1%}",
            "max drawdown": f"{m['max_drawdown']:.1%}",
            "Sharpe": f"{m['sharpe']:.2f}",
        }
    print(f"\n=== {title}: {start.date()} -> {end.date()} ({settings.base_currency}) ===")
    print(pd.DataFrame(rows).T.to_string())


if __name__ == "__main__":
    print("Target weights:", {k: round(v, 4) for k, v in blended_weights().items()})
    report(
        "Full sleeve (limited by MEEQ)",
        {
            "SPY buy&hold": {"SPY": 1.0},
            "60/40": CLASSIC,
            "Sleeve only": SLEEVE,
            "Blend, unhedged": blended_weights(hedge_share=0.0),
            "Blend, 5% hedged": blended_weights(),
        },
    )
    report(
        "Longer window, MEEQ folded into EXSA (limited by PAVE)",
        {
            "SPY buy&hold": {"SPY": 1.0},
            "60/40": CLASSIC,
            "Sleeve only": SLEEVE_LONG,
            "Blend, unhedged": blended_weights(SLEEVE_LONG, hedge_share=0.0),
            "Blend, 5% hedged": blended_weights(SLEEVE_LONG),
        },
    )
