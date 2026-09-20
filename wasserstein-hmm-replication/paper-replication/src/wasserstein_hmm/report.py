"""PURPOSE: produce the replication figures.
INPUTS: backtests, published targets, and reproduced metrics.
OUTPUTS: PNG figures.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .backtest import Backtest


def _wealth(returns: pd.Series) -> pd.Series:
    return (1 + returns).cumprod()


WEIGHT_COLORS = {
    "SPY": "#1f4e79", "TLT": "#5b9bd5", "GLD": "#d4a017", "USO": "#5c5c5c", "UUP": "#7fb069",
}


def plot_weights_and_turnover(
    weights: pd.DataFrame, hmm_turnover: pd.Series, knn_turnover: pd.Series, path: Path,
) -> None:
    """Stacked daily weights (top) and 21-session average one-way turnover (bottom)."""
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(9.0, 6.6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]},
    )
    colors = [WEIGHT_COLORS.get(c, None) for c in weights.columns]
    top.stackplot(
        weights.index, weights.T.to_numpy(), labels=list(weights.columns),
        colors=colors, linewidth=0.4, edgecolor="white",
    )
    top.set(ylim=(0, 1), ylabel="Portfolio weight", title="Wasserstein-HMM portfolio weights")
    top.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    top.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=len(weights.columns),
        frameon=False, fontsize=9,
    )
    top.margins(x=0)
    bottom.plot(knn_turnover.rolling(21).mean(), color="#c0504d", lw=1.4, label="KNN")
    bottom.plot(hmm_turnover.rolling(21).mean(), color="#1f4e79", lw=1.4, label="HMM")
    bottom.set(
        ylabel="One-way turnover", ylim=(0, 0.9),
        title="Daily turnover, 21-session moving average",
    )
    bottom.legend(frameon=False, loc="upper right", ncol=2)
    bottom.margins(x=0)
    for axis in (top, bottom):
        axis.grid(axis="y", alpha=0.3 if axis is bottom else 0.0)
        axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def create_figures(
    directory: Path,
    hmm: Backtest,
    knn: Backtest,
    passive: dict[str, pd.Series],
    published: dict[str, dict[str, float]],
    reproduced: dict[str, dict[str, float]],
) -> list[Path]:
    out = directory / "figures"
    out.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    paths: list[Path] = []

    fig, ax = plt.subplots(figsize=(8.0, 4.3))
    ax.plot(_wealth(hmm.gross_returns), label="Wasserstein HMM replication", lw=1.5)
    ax.plot(_wealth(knn.gross_returns), label="KNN replication", lw=1.0)
    ax.plot(_wealth(passive["equal_weight"]), label="Equal weight", lw=1.0)
    ax.plot(_wealth(passive["spx"]), label="SPY buy & hold", lw=1.0)
    ax.set(title="Out-of-sample growth of one dollar", ylabel="Wealth")
    ax.legend(ncol=2)
    path = out / "cumulative_performance.png"
    fig.tight_layout(); fig.savefig(path, dpi=220); plt.close(fig); paths.append(path)

    path = out / "weights_and_turnover.png"
    plot_weights_and_turnover(hmm.weights, hmm.turnover, knn.turnover, path)
    paths.append(path)

    methods = ["wasserstein_hmm", "knn", "equal_weight", "spx"]
    labels = ["HMM", "KNN", "Equal", "SPX"]
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.6))
    x = range(len(methods))
    width = 0.36
    axes[0].bar([i - width / 2 for i in x], [published[m]["sharpe"] for m in methods], width, label="Published")
    axes[0].bar([i + width / 2 for i in x], [reproduced[m]["sharpe"] for m in methods], width, label="Reproduced")
    axes[0].set(title="Annualized Sharpe", xticks=list(x), xticklabels=labels)
    axes[0].legend(fontsize=8)
    axes[1].bar([i - width / 2 for i in x], [published[m]["max_drawdown"] for m in methods], width)
    axes[1].bar([i + width / 2 for i in x], [reproduced[m]["max_drawdown"] for m in methods], width)
    axes[1].set(title="Maximum drawdown", xticks=list(x), xticklabels=labels)
    path = out / "published_vs_reproduced.png"
    fig.tight_layout(); fig.savefig(path, dpi=220); plt.close(fig); paths.append(path)
    return paths
