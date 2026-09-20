"""PURPOSE: compare interpolation rules for the SPY/TLT plus GLD/SLV thesis.
INPUTS: thesis.yaml, strategy.py, and the thesispaper adjusted-price cache.
OUTPUTS: comparison JSON/macros, trade ledger, and publication figures.
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

from strategy import ASSETS, MetalsHedgedFrontier

from thesispaper import metrics as m
from thesispaper.backtest import BacktestResult, run
from thesispaper.data import load_prices
from thesispaper.figures import style
from thesispaper.spec import load_spec

VARIANTS = ("sine", "linear", "polynomial")
COLORS = {"sine": "#0072B2", "linear": "#009E73", "polynomial": "#CC79A7"}


class FixedMix:
    def __init__(self, weights: dict[str, float]) -> None:
        self.target = pd.Series(weights, dtype=float)

    def weights(self, history: pd.DataFrame) -> pd.Series:
        return self.target.reindex(history.columns).fillna(0.0)


def performance(r: pd.Series) -> dict[str, float]:
    return {"total_return": m.total_return(r), "cagr": m.cagr(r), "vol": m.ann_vol(r),
            "sharpe": m.sharpe(r), "max_drawdown": m.max_drawdown(r)}


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
    strategy = MetalsHedgedFrontier({**params, "interpolation": "sine"})
    rows = []
    for end in range(1, len(prices)):
        history = prices.iloc[:end]
        state = strategy.state(history)
        rows.append({"date": prices.index[end], "short_vol": state.short_volatility,
                     "long_vol": state.long_volatility, "growth_gap": state.growth_gap,
                     "raw": state.raw_coordinate, "smoothed": strategy.coordinate(history),
                     "anchor_metals": state.anchor_metals,
                     "gmv_metals": state.minimum_variance_metals,
                     "high_risk_metals": state.high_risk_metals})
    return pd.DataFrame(rows).set_index("date")


def make_figures(
    prices: pd.DataFrame,
    runs: dict[str, BacktestResult],
    hedged: BacktestResult,
    unhedged: BacktestResult,
    signals: pd.DataFrame,
    costs: dict[str, dict[str, list[float]]],
    params: dict[str, Any],
) -> None:
    style()
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.0), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    sine_wealth = m.wealth(runs["sine"].returns)
    axes[0].plot(sine_wealth, color=COLORS["sine"], lw=1.6, label="Dynamic sine")
    axes[0].plot(m.wealth(hedged.returns), color="#E69F00", lw=1.35,
                 label="Static metals hedge")
    axes[0].plot(m.wealth(unhedged.returns), color="#009E73", lw=1.15,
                 label="Static 60/40")
    axes[0].plot(prices["SPY"] / prices["SPY"].iloc[0], color="#666666", lw=0.9,
                 label="SPY")
    axes[0].set(title="Core plus metals: growth of one dollar", ylabel="Wealth")
    axes[0].legend(ncol=2, loc="upper left")
    for name in ("linear", "polynomial"):
        relative = (m.wealth(runs[name].returns) / sine_wealth - 1.0) * 10_000
        axes[1].plot(relative, color=COLORS[name], lw=1.0, label=f"{name.title()} vs sine")
    axes[1].axhline(0, color="#555555", lw=0.7)
    axes[1].set(ylabel="Difference\n(bps)", xlabel="Date")
    axes[1].legend(ncol=2, loc="best")
    save(fig, "fig_metals_wealth")

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.8), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    metals_paths = {name: bt.weights["GLD"] + bt.weights["SLV"]
                    for name, bt in runs.items()}
    axes[0].plot(metals_paths["sine"], color=COLORS["sine"], lw=1.35,
                 label="Sine target")
    axes[0].axhline(0.20, color="#E69F00", lw=1.0, ls="--", label="20% reference")
    axes[0].axhspan(0.05, 0.35, color="#0072B2", alpha=0.05, label="Allowed range")
    axes[0].set(title="Daily precious-metals target", ylabel="GLD + SLV", ylim=(0, 0.40))
    axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    axes[0].legend(ncol=3, loc="upper left")
    for name in ("linear", "polynomial"):
        delta = (metals_paths[name] - metals_paths["sine"]) * 100
        axes[1].plot(delta, color=COLORS[name], lw=0.9, label=f"{name.title()} - sine")
    axes[1].axhline(0, color="#555555", lw=0.7)
    axes[1].set(ylabel="Difference\n(pct. points)", xlabel="Date")
    axes[1].legend(ncol=2, loc="best")
    save(fig, "fig_metals_weights")

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.1), sharex=True)
    axes[0].plot(signals["short_vol"], color="#D55E00", lw=0.75, alpha=0.65,
                 label="5-session")
    axes[0].plot(signals["long_vol"], color="#0072B2", lw=1.35, label="21-session")
    axes[0].set(title="Hedged-reference volatility", ylabel="Annualised volatility")
    axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    axes[0].legend()
    axes[1].plot(signals["raw"], color="#999999", lw=0.5, alpha=0.3,
                 label="Raw coordinate")
    axes[1].plot(signals["smoothed"], color=COLORS["sine"], lw=1.35,
                 label="Sine-smoothed")
    axes[1].axhline(0, color="#444444", lw=0.7)
    axes[1].set(title="Growth-gated frontier coordinate", ylabel="+ de-risk / - add risk")
    axes[1].legend()
    save(fig, "fig_metals_signal")

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    line_styles = {"sine": "-", "linear": "--", "polynomial": ":"}
    markers = {"sine": "o", "linear": "s", "polynomial": "^"}
    for name in VARIANTS:
        axes[0].plot(costs[name]["bps"], costs[name]["sharpe"],
                     color=COLORS[name], ls=line_styles[name], marker=markers[name],
                     ms=4.5, lw=1.4, label=name.title())
    axes[0].set(title="Interpolation ranking across trading costs",
                ylabel="Annualised Sharpe")
    axes[0].legend(ncol=3, loc="best")
    sine_costs = np.asarray(costs["sine"]["sharpe"])
    for name in ("linear", "polynomial"):
        delta = (np.asarray(costs[name]["sharpe"]) - sine_costs) * 100
        axes[1].plot(costs[name]["bps"], delta, color=COLORS[name],
                     ls=line_styles[name], marker=markers[name], ms=4, lw=1.1,
                     label=f"{name.title()} - sine")
    axes[1].axhline(0, color="#555555", lw=0.7)
    axes[1].set(xlabel="Cost per unit turnover (basis points)",
                ylabel="Sharpe delta\n(x100)")
    axes[1].legend(ncol=2, loc="best")
    save(fig, "fig_metals_costs")

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.plot(m.drawdown_series(hedged.returns), color="#E69F00", lw=1.35,
            label="Static metals hedge")
    ax.plot(m.drawdown_series(unhedged.returns), color="#0072B2", lw=1.2,
            label="Static 60/40")
    ax.axhline(0, color="#555555", lw=0.7)
    ax.set(title="Does the metals sleeve hedge drawdown?", ylabel="Drawdown")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.legend()
    save(fig, "fig_metals_hedge_drawdown")

    latest = MetalsHedgedFrontier({**params, "interpolation": "sine"})
    returns = prices.pct_change().dropna()
    metals, expected, volatility, gmv_i, anchor_i = latest._frontier(returns)
    target = float(latest.weights(prices)[["GLD", "SLV"]].sum())
    target_i = int(np.argmin(np.abs(metals - target)))
    reference_i = int(np.argmin(np.abs(metals - 0.20)))
    fig, ax = plt.subplots(figsize=(5.5, 3.9))
    ax.plot(volatility, expected, color="#0072B2", lw=1.4, label="Two-sleeve frontier")
    point_groups: dict[int, list[str]] = {}
    for idx, label in ((gmv_i, "GMV"), (anchor_i, "anchor"), (target_i, "target")):
        point_groups.setdefault(idx, []).append(label)
    for idx, labels in point_groups.items():
        label = "Latest " + " = ".join(labels)
        ax.scatter(volatility[idx], expected[idx], s=52, color="#CC79A7", marker="o",
                   edgecolor="white", linewidth=0.7, label=label, zorder=4)
        ax.annotate(f"{metals[idx]:.0%} metals", (volatility[idx], expected[idx]),
                    xytext=(7, -14), textcoords="offset points", fontsize=8)
    ax.scatter(volatility[reference_i], expected[reference_i], s=48, color="#E69F00", marker="D",
               edgecolor="white", linewidth=0.7, label="Static 20% reference", zorder=4)
    ax.annotate("20% metals", (volatility[reference_i], expected[reference_i]),
                xytext=(7, 7), textcoords="offset points", fontsize=8)
    ax.set(title="Latest core/metals frontier", xlabel="Annualised volatility",
           ylabel="Estimated annual return")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.legend()
    save(fig, "fig_metals_frontier")


def main() -> None:
    spec = load_spec("metals_hedged_frontier", ROOT)
    prices = load_prices(spec)
    params = dict(spec.strategy_params)
    runs = {name: run(prices[ASSETS],
                      MetalsHedgedFrontier({**params, "interpolation": name}),
                      spec.costs_bps, "daily") for name in VARIANTS}
    hedged_weights = {"SPY": 0.48, "TLT": 0.32, "GLD": 0.14, "SLV": 0.06}
    core_weights = {"SPY": 0.60, "TLT": 0.40, "GLD": 0.0, "SLV": 0.0}
    hedged = run(prices[ASSETS], FixedMix(hedged_weights), spec.costs_bps, "daily")
    unhedged = run(prices[ASSETS], FixedMix(core_weights), spec.costs_bps, "daily")
    cost_grid = [0.0, 5.0, 10.0, 25.0, 50.0]
    costs: dict[str, dict[str, list[float]]] = {}
    for name in VARIANTS:
        values = []
        for cost in cost_grid:
            bt = run(prices[ASSETS], MetalsHedgedFrontier({**params, "interpolation": name}),
                     cost, "daily")
            values.append(m.sharpe(bt.returns))
        costs[name] = {"bps": cost_grid, "sharpe": values}
    signals = signal_frame(prices[ASSETS], params)
    perf = {name: performance(bt.returns) for name, bt in runs.items()}
    perf["static_hedged"] = performance(hedged.returns)
    perf["static_core"] = performance(unhedged.returns)
    turnover = {name: float(bt.turnover.mean()) for name, bt in runs.items()}
    rankings = [tuple(sorted(VARIANTS, key=lambda n: costs[n]["sharpe"][i], reverse=True))
                for i in range(len(cost_grid))]
    h1 = perf["sine"]["sharpe"] > perf["static_hedged"]["sharpe"]
    h2 = perf["static_hedged"]["max_drawdown"] > perf["static_core"]["max_drawdown"]
    h3 = len(set(rankings)) > 1
    latest_strategy = MetalsHedgedFrontier({**params, "interpolation": "sine"})
    latest_weights = latest_strategy.weights(prices[ASSETS])
    result = {
        "sample": {"start": str(prices.index[0].date()), "end": str(prices.index[-1].date()),
                   "observations": len(prices) - 1},
        "performance": perf, "average_turnover": turnover,
        "cost_sensitivity": costs, "cost_rankings": rankings,
        "hypotheses": {"H1": h1, "H2": h2, "H3": h3},
        "latest": {"date": str(prices.index[-1].date()),
                   **{symbol: float(latest_weights[symbol]) for symbol in ASSETS},
                   "smoothed_coordinate": float(latest_strategy.coordinate(prices[ASSETS]))},
    }
    (HERE / "comparison_results.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["% generated by analysis.py; do not edit"]
    prefixes = {"sine": "Sine", "linear": "Linear", "polynomial": "Polynomial",
                "static_hedged": "Hedged", "static_core": "Core"}
    for key, prefix in prefixes.items():
        for metric, suffix, kind in (("cagr", "CAGR", "pct"), ("vol", "Vol", "pct"),
                                     ("sharpe", "Sharpe", "num"),
                                     ("max_drawdown", "MaxDD", "pct")):
            lines.append(macro(prefix + suffix, perf[key][metric], kind))
    for name, prefix in (("sine", "Sine"), ("linear", "Linear"),
                         ("polynomial", "Polynomial")):
        lines.append(macro(prefix + "Turnover", turnover[name], "pct"))
    lines.extend([macro("HOneResult", "Supported" if h1 else "Not supported"),
                  macro("HTwoResult", "Supported" if h2 else "Not supported"),
                  macro("HThreeResult", "Supported" if h3 else "Not supported"),
                  macro("LatestModelDate", result["latest"]["date"]),
                  macro("LatestModelCoordinate", result["latest"]["smoothed_coordinate"], "num")])
    for symbol in ASSETS:
        lines.append(macro("Latest" + symbol, result["latest"][symbol], "pct"))
    (HERE / "comparison_numbers.tex").write_text("\n".join(lines) + "\n")
    ledger = runs["sine"].weights.rename(columns={s: f"{s.lower()}_target" for s in ASSETS})
    for symbol in ASSETS:
        col = f"{symbol.lower()}_target"
        ledger[f"{symbol.lower()}_change"] = ledger[col].diff().fillna(ledger[col])
    ledger["turnover"] = runs["sine"].turnover
    ledger.to_csv(HERE / "model_trade_ledger.csv", index_label="date")
    pd.DataFrame([result["latest"]]).to_csv(HERE / "latest_model_weights.csv", index=False)
    make_figures(prices[ASSETS], runs, hedged, unhedged, signals, costs, params)
    print(f"wrote comparison outputs through {result['latest']['date']}")


if __name__ == "__main__":
    main()
