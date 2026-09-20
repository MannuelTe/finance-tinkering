"""PURPOSE: compare interpolation kernels and generate thesis-specific outputs.
INPUTS: thesis.yaml, strategy.py, and the thesispaper price cache.
OUTPUTS: comparison JSON/macros, CSV trade ledger, and publication figures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy import VolatilityFrontier

from thesispaper import metrics as m
from thesispaper.backtest import BacktestResult, run
from thesispaper.data import load_prices
from thesispaper.figures import style
from thesispaper.spec import load_spec

VARIANTS = ("sine", "linear", "polynomial")
COLORS = {"sine": "#0072B2", "linear": "#009E73", "polynomial": "#CC79A7"}


class StaticMix:
    def weights(self, history: pd.DataFrame) -> pd.Series:
        return pd.Series({"SPY": 0.60, "TLT": 0.40}).reindex(history.columns).fillna(0.0)


def performance(r: pd.Series) -> dict[str, float]:
    return {
        "total_return": m.total_return(r),
        "cagr": m.cagr(r),
        "vol": m.ann_vol(r),
        "sharpe": m.sharpe(r),
        "max_drawdown": m.max_drawdown(r),
    }


def save(fig: plt.Figure, name: str) -> None:
    out = HERE / "figures"
    out.mkdir(exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(out / f"{name}.{suffix}", dpi=220)
    plt.close(fig)


def macro(name: str, value: Any, kind: str = "text") -> str:
    if kind == "pct":
        rendered = f"{100 * float(value):.2f}\\%"
    elif kind == "num":
        rendered = f"{float(value):.2f}"
    else:
        rendered = str(value).replace("_", "\\_").replace("%", "\\%")
    return f"\\newcommand{{\\{name}}}{{{rendered}}}"


def signal_frame(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    strategy = VolatilityFrontier({**params, "interpolation": "sine"})
    rows = []
    for end in range(1, len(prices)):
        history = prices.iloc[:end]
        state = strategy.state(history)
        rows.append({
            "date": prices.index[end],
            "short_vol": state.short_volatility,
            "long_vol": state.long_volatility,
            "growth_gap": state.growth_gap,
            "raw": state.raw_coordinate,
            "smoothed": strategy.coordinate(history),
            "anchor_spy": state.anchor_spy,
            "gmv_spy": state.minimum_variance_spy,
            "high_risk_spy": state.high_risk_spy,
        })
    return pd.DataFrame(rows).set_index("date")


def make_figures(
    prices: pd.DataFrame,
    runs: dict[str, BacktestResult],
    static: BacktestResult,
    signals: pd.DataFrame,
    costs: dict[str, dict[str, list[float]]],
    params: dict[str, Any],
) -> None:
    style()
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for name, bt in runs.items():
        ax.plot(m.wealth(bt.returns), color=COLORS[name], lw=1.25, label=name.title())
    ax.plot(m.wealth(static.returns), color="#E69F00", lw=1.1, label="Static 60/40")
    ax.plot(prices["SPY"] / prices["SPY"].iloc[0], color="#666666", lw=0.9, label="SPY")
    ax.set(title="Interpolation comparison: growth of one dollar", ylabel="Wealth")
    ax.legend(ncol=3)
    save(fig, "fig_interpolation_wealth")

    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    for name, bt in runs.items():
        ax.plot(bt.weights["SPY"], color=COLORS[name], lw=1.05, label=name.title())
    ax.axhline(0.60, color="#E69F00", lw=1.0, ls="--", label="60/40 reference")
    ax.set(title="Daily target equity weight", ylabel="SPY weight", ylim=(0, 1))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.legend(ncol=2)
    save(fig, "fig_interpolation_weights")

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.1), sharex=True)
    axes[0].plot(signals["short_vol"], color="#D55E00", lw=1.0, label="5-session")
    axes[0].plot(signals["long_vol"], color="#0072B2", lw=1.0, label="21-session")
    axes[0].set(title="Reference-portfolio volatility estimates", ylabel="Annualised volatility")
    axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    axes[0].legend()
    axes[1].plot(signals["raw"], color="#999999", lw=0.75, alpha=0.8, label="Raw coordinate")
    axes[1].plot(signals["smoothed"], color=COLORS["sine"], lw=1.1, label="Sine interpolation")
    axes[1].axhline(0, color="#444444", lw=0.7)
    axes[1].set(title="Growth-gated frontier coordinate", ylabel="+ de-risk / - add risk")
    axes[1].legend()
    save(fig, "fig_signal_diagnostics")

    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for name in VARIANTS:
        ax.plot(costs[name]["bps"], costs[name]["sharpe"], "o-", color=COLORS[name], label=name.title())
    ax.set(title="Interpolation ranking across trading-cost assumptions",
           xlabel="Cost per unit turnover (basis points)", ylabel="Annualised Sharpe")
    ax.legend()
    save(fig, "fig_interpolation_costs")

    latest = VolatilityFrontier({**params, "interpolation": "sine"})
    returns = prices.pct_change().dropna()
    spy, expected, volatility, gmv_i, anchor_i = latest._frontier(returns)
    target = latest.weights(prices)["SPY"]
    target_i = int(np.argmin(np.abs(spy - target)))
    fig, ax = plt.subplots(figsize=(5.3, 3.8))
    ax.plot(volatility, expected, color="#0072B2", lw=1.4, label="Feasible frontier grid")
    for idx, label, color in ((gmv_i, "Minimum variance", "#009E73"),
                              (anchor_i, "Growth-optimal anchor", "#D55E00"),
                              (target_i, "Latest sine target", "#CC79A7")):
        ax.scatter(volatility[idx], expected[idx], s=34, color=color, label=label, zorder=3)
    ax.set(title="Latest rolling SPY/TLT frontier", xlabel="Annualised volatility",
           ylabel="Estimated annual return")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.legend()
    save(fig, "fig_latest_frontier")


def main() -> None:
    spec = load_spec("volatility_frontier", ROOT)
    prices = load_prices(spec)
    params = dict(spec.strategy_params)
    runs = {
        name: run(prices[spec.universe], VolatilityFrontier({**params, "interpolation": name}),
                  spec.costs_bps, spec.rebalance)
        for name in VARIANTS
    }
    static = run(prices[spec.universe], StaticMix(), spec.costs_bps, spec.rebalance)
    cost_grid = [0.0, 5.0, 10.0, 25.0, 50.0]
    costs: dict[str, dict[str, list[float]]] = {}
    for name in VARIANTS:
        sharpes = []
        for cost in cost_grid:
            result = run(prices[spec.universe],
                         VolatilityFrontier({**params, "interpolation": name}), cost, "daily")
            sharpes.append(m.sharpe(result.returns))
        costs[name] = {"bps": cost_grid, "sharpe": sharpes}
    signals = signal_frame(prices[spec.universe], params)
    perf = {name: performance(bt.returns) for name, bt in runs.items()}
    perf["static_60_40"] = performance(static.returns)
    turnover = {name: float(bt.turnover.mean()) for name, bt in runs.items()}
    rankings = [tuple(sorted(VARIANTS, key=lambda n: costs[n]["sharpe"][i], reverse=True))
                for i in range(len(cost_grid))]
    h1 = perf["sine"]["sharpe"] > perf["static_60_40"]["sharpe"]
    h3 = len(set(rankings)) > 1
    latest_strategy = VolatilityFrontier({**params, "interpolation": "sine"})
    latest_weights = latest_strategy.weights(prices[spec.universe])
    result = {
        "sample": {"start": str(prices.index[0].date()), "end": str(prices.index[-1].date()),
                   "observations": len(prices) - 1},
        "performance": perf,
        "average_turnover": turnover,
        "cost_sensitivity": costs,
        "cost_rankings": rankings,
        "hypotheses": {"H1": h1, "H2": True, "H3": h3},
        "latest": {"date": str(prices.index[-1].date()),
                   "SPY": float(latest_weights["SPY"]), "TLT": float(latest_weights["TLT"]),
                   "smoothed_coordinate": float(latest_strategy.coordinate(prices[spec.universe]))},
    }
    (HERE / "comparison_results.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["% generated by analysis.py from comparison_results.json; do not edit"]
    prefixes = {"sine": "Sine", "linear": "Linear", "polynomial": "Polynomial",
                "static_60_40": "Static"}
    for key, prefix in prefixes.items():
        for metric, suffix, kind in (("cagr", "CAGR", "pct"), ("vol", "Vol", "pct"),
                                     ("sharpe", "Sharpe", "num"),
                                     ("max_drawdown", "MaxDD", "pct")):
            lines.append(macro(prefix + suffix, perf[key][metric], kind))
    for name, prefix in (("sine", "Sine"), ("linear", "Linear"), ("polynomial", "Polynomial")):
        lines.append(macro(prefix + "Turnover", turnover[name], "pct"))
    lines.extend([
        macro("HOneResult", "Supported" if h1 else "Not supported"),
        macro("HTwoResult", "Supported by construction"),
        macro("HThreeResult", "Supported" if h3 else "Not supported"),
        macro("LatestModelDate", result["latest"]["date"]),
        macro("LatestModelSPY", result["latest"]["SPY"], "pct"),
        macro("LatestModelTLT", result["latest"]["TLT"], "pct"),
        macro("LatestModelCoordinate", result["latest"]["smoothed_coordinate"], "num"),
    ])
    (HERE / "comparison_numbers.tex").write_text("\n".join(lines) + "\n")
    ledger = runs["sine"].weights.rename(columns={"SPY": "spy_target", "TLT": "tlt_target"})
    ledger["spy_change"] = ledger["spy_target"].diff().fillna(ledger["spy_target"])
    ledger["tlt_change"] = ledger["tlt_target"].diff().fillna(ledger["tlt_target"])
    ledger["turnover"] = runs["sine"].turnover
    ledger.to_csv(HERE / "model_trade_ledger.csv", index_label="date")
    pd.DataFrame([result["latest"]]).to_csv(HERE / "latest_model_weights.csv", index=False)
    make_figures(prices, runs, static, signals, costs, params)
    print(f"wrote comparison outputs through {result['latest']['date']}")


if __name__ == "__main__":
    main()
