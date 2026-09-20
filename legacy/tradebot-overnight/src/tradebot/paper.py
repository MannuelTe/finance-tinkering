"""Research tables for the volatility-aware overnight SPY strategy (pure functions, no network).

Strategy under study
--------------------
The portfolio's SPY slice (its target weight, 27%) is managed only by the daily overnight rule:
at the decision time (60 minutes before the close, 15:00 ET) the model looks at the overnight
edge and at volatility (overnight, daily, and today's realized intraday volatility up to that
moment). Either the whole slice is held from that close to the next open, or SPY is not touched
that day. Every other ETF follows the normal target weights, rebalanced daily.

Return accounting (daily, in the base currency)

    r_total[t] = r_rest[t] + spy_weight * slice_return[t]

`r_rest` is the return of the non-SPY holdings (the SPY slice sits in cash while it is not
invested, 0% interest). `slice_return[t]` is the overnight leg that ends at the open of day t:
`weight * (open_t / close_{t-1} - 1 - cost)`, with `cost` the ALL-IN round-trip cost per invested
dollar. The overnight leg is computed in USD, so FX moves during the overnight hold are ignored
(the non-SPY holdings do carry their currency conversion). Costs exclude tax, interest and
commissions minimums. Daily rebalancing to the target weights is assumed, as in the rest of the
backtests.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from tradebot import overnight
from tradebot.overnight import OvernightConfig

TRADING_DAYS = overnight.TRADING_DAYS

# Strategy keys -> display names (also the CSV column names of the equity table).
STRATEGIES = {
    "vol_aware": "Vol-aware overnight SPY + rest",
    "binary_ev": "Overnight SPY, binary EV rule (no vol filter)",
    "always": "Overnight SPY every day (no model)",
    "cash": "SPY slice in cash + rest",
    "blend_hold": "Blend, SPY held continuously",
    "classic": "60/40 (SPY/TLT)",
    "spy": "SPY buy & hold",
}


def slice_table(
    daily: pd.DataFrame, intraday_var: pd.Series | None, config: OvernightConfig
) -> pd.DataFrame:
    """Per-decision table from the overnight backtest, indexed by SALE date."""
    return overnight.backtest(daily, config, initial=1.0, intraday=intraday_var)


def rest_returns(nav: pd.Series) -> pd.Series:
    """Daily returns of the non-SPY holdings from a `run_backtest` NAV path."""
    return nav.pct_change().dropna()


def combine(rest: pd.Series, slice_ret: pd.Series, spy_weight: float) -> pd.Series:
    """Daily total return on the dates both parts cover."""
    both = pd.concat({"rest": rest, "slice": slice_ret}, axis=1).dropna()
    return both["rest"] + spy_weight * both["slice"]


def to_equity(returns: pd.Series, start: float = 100.0) -> pd.Series:
    return start * (1 + returns).cumprod()


def metrics(returns: pd.Series) -> dict[str, float]:
    """Annualized figures from a daily return series (risk-free rate 0)."""
    r = returns.dropna()
    if len(r) < 2:
        return {}
    equity = np.r_[1.0, (1 + r).cumprod().to_numpy()]
    total = float(equity[-1] - 1)
    years = len(r) / TRADING_DAYS
    vol = float(r.std(ddof=0) * math.sqrt(TRADING_DAYS))
    return {
        "sessions": len(r),
        "total_return": total,
        "cagr": float((1 + total) ** (1 / years) - 1) if years > 0 else float("nan"),
        "volatility": vol,
        "sharpe": float(r.mean() * TRADING_DAYS / vol) if vol > 0 else float("nan"),
        "max_drawdown": float((equity / np.maximum.accumulate(equity) - 1).min()),
    }


def decision_export(table: pd.DataFrame, intraday: pd.DataFrame | None) -> pd.DataFrame:
    """Flat decision log for plotting: one row per decision day, with what happened next."""
    out = pd.DataFrame(
        {
            "decision_date": table["decision_date"],
            "sale_date": table.index,
            "traded": table["weight"] > 0,
            "raw_weight": table["raw_weight"],
            "weight": table["weight"],
            "mu": table["mu"],
            "sigma_overnight": table["sigma_overnight"],
            "sigma_daily": table["sigma_daily"],
            "sigma_intraday": table["sigma_intraday"].astype(float),
            "risk_sigma": table["risk_sigma"],
            "intraday_missing": table["intraday_missing"],
            "next_overnight_return": table["overnight_return"],
            "slice_return": table["strategy_return"],
        }
    ).reset_index(drop=True)
    if intraday is not None and not intraday.empty:
        iv = intraday["intraday_var"].rename("intraday_var")
        out = out.merge(iv, left_on="decision_date", right_index=True, how="left")
    return out


def build_tables(
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    rest_nav: pd.Series,
    baseline_navs: dict[str, pd.Series],
    spy_weight: float,
    *,
    cost_bps: float = 2.0,
    min_weight: float = 0.5,
    min_weight_grid: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5, 0.75, 1.0),
    cost_grid: tuple[float, ...] = (0.0, 2.0, 5.0, 10.0),
    window: int = 60,
) -> dict[str, pd.DataFrame]:
    """Everything the paper's figures need.

    daily: SPY open/close (split AND dividend adjusted), date-indexed.
    intraday: output of `overnight.intraday_variance_by_day`.
    rest_nav: NAV path of the non-SPY holdings alone (SPY slice idle in cash).
    baseline_navs: NAV paths keyed 'blend_hold', 'classic', 'spy'.
    """
    iv = intraday["intraday_var"] if not intraday.empty else pd.Series(dtype=float)

    def cfg(**kw) -> OvernightConfig:
        base = {"window": window, "cost_bps": cost_bps, "binary": True, "min_weight": min_weight}
        return OvernightConfig(**{**base, **kw})

    proposed = slice_table(daily, iv, cfg())
    binary_ev = slice_table(daily, None, cfg(min_weight=0.0))
    rest = rest_returns(rest_nav)

    cost = cost_bps / 10_000
    slices = {
        "vol_aware": proposed["strategy_return"],
        "binary_ev": binary_ev["strategy_return"],
        "always": proposed["overnight_return"] - cost,
        "cash": pd.Series(0.0, index=proposed.index),
    }
    returns = {k: combine(rest, v, spy_weight) for k, v in slices.items()}
    for key, nav in baseline_navs.items():
        returns[key] = nav.pct_change().dropna()

    frame = pd.concat(returns, axis=1, sort=True).dropna()
    frame.index.name = "date"
    frame = frame[[k for k in STRATEGIES if k in frame.columns]]
    equity = frame.apply(to_equity)
    equity.loc[frame.index[0] - pd.Timedelta(days=1)] = 100.0
    equity = equity.sort_index()
    equity.index.name = "date"

    summary = pd.DataFrame({STRATEGIES[k]: metrics(frame[k]) for k in frame.columns}).T
    summary.index.name = "strategy"
    summary.insert(0, "key", [k for k in frame.columns])

    def sweep(param: str, values: tuple[float, ...]) -> pd.DataFrame:
        rows = []
        for value in values:
            t = slice_table(daily, iv, cfg(**{param: value}))
            r = combine(rest, t["strategy_return"], spy_weight).reindex(frame.index).dropna()
            rows.append({param: value, "trade_fraction": float((t["weight"] > 0).mean()), **metrics(r)})
        return pd.DataFrame(rows)

    decisions = decision_export(proposed, intraday)
    window_info = pd.DataFrame(
        [
            {
                "start": frame.index[0].date().isoformat(),
                "end": frame.index[-1].date().isoformat(),
                "sessions": len(frame),
                "decision_days": len(proposed),
                "decision_days_with_intraday": int((~proposed["intraday_missing"]).sum()),
                "traded_days": int((proposed["weight"] > 0).sum()),
                "spy_weight": spy_weight,
                "cost_bps_roundtrip": cost_bps,
                "min_weight": min_weight,
                "model_window": window,
            }
        ]
    )
    return {
        "equity": equity.reset_index(),
        "returns": frame.reset_index(),
        "summary": summary.reset_index(),
        "decisions": decisions,
        "sensitivity_min_weight": sweep("min_weight", min_weight_grid),
        "sensitivity_cost": sweep("cost_bps", cost_grid),
        "window": window_info,
    }
