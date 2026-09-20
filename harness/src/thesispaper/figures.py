"""Generic paper figures (Okabe-Ito palette, serif, PDF + PNG).

PURPOSE: equity, drawdown, rolling Sharpe, return distribution, cost-sensitivity figures.
INPUTS: net strategy returns, benchmark returns (pd.Series, same index), output directory.
OUTPUTS: <out_dir>/fig_<name>.pdf and .png; each function returns the list of written paths.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from thesispaper import metrics as m

C_STRAT, C_BENCH = "#0072B2", "#D55E00"
WIDTH = 7.2


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 220, "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "Times"], "font.size": 9,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.labelsize": 9,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.color": "#dddddd", "grid.linewidth": 0.6, "legend.frameon": False,
        "legend.fontsize": 8, "figure.constrained_layout.use": True,
    })


def _save(fig: plt.Figure, out_dir: Path, name: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{name}.pdf", out_dir / f"{name}.png"]
    for p in paths:
        fig.savefig(p)
    plt.close(fig)
    return paths


def fig_equity(r: pd.Series, b: pd.Series, out_dir: Path, labels=("Strategy", "Benchmark")):
    style()
    fig, ax = plt.subplots(figsize=(WIDTH, 3.4))
    ax.plot(m.wealth(r), color=C_STRAT, lw=1.4, label=labels[0])
    ax.plot(m.wealth(b), color=C_BENCH, lw=1.2, label=labels[1])
    ax.set(title="Growth of 1 unit of wealth", ylabel="Wealth (start = 1)")
    ax.legend()
    return _save(fig, out_dir, "fig_equity")


def fig_drawdown(r: pd.Series, b: pd.Series, out_dir: Path, labels=("Strategy", "Benchmark")):
    style()
    fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
    ax.fill_between(r.index, m.drawdown_series(r), 0, color=C_STRAT, alpha=0.5, label=labels[0])
    ax.plot(m.drawdown_series(b), color=C_BENCH, lw=1.0, label=labels[1])
    ax.set(title="Drawdown from running peak", ylabel="Drawdown")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(loc="lower left")
    return _save(fig, out_dir, "fig_drawdown")


def fig_rolling_sharpe(r: pd.Series, b: pd.Series, out_dir: Path, window: int = 126,
                       labels=("Strategy", "Benchmark")):
    style()
    fig, ax = plt.subplots(figsize=(WIDTH, 3.0))
    ax.plot(m.rolling_sharpe(r, window), color=C_STRAT, lw=1.2, label=labels[0])
    ax.plot(m.rolling_sharpe(b, window), color=C_BENCH, lw=1.0, label=labels[1])
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set(title=f"Rolling {window}-day Sharpe ratio", ylabel="Annualised Sharpe")
    ax.legend()
    return _save(fig, out_dir, "fig_rolling_sharpe")


def fig_distribution(r: pd.Series, out_dir: Path):
    style()
    fig, ax = plt.subplots(figsize=(WIDTH / 1.6, 3.2))
    ax.hist(r, bins=60, density=True, color=C_STRAT, alpha=0.6, label="Daily returns")
    mle = m.gaussian_mle(r)
    xs = np.linspace(r.min(), r.max(), 300)
    pdf = np.exp(-((xs - mle.mu) ** 2) / (2 * mle.var)) / np.sqrt(2 * np.pi * mle.var)
    ax.plot(xs, pdf, color=C_BENCH, lw=1.4, label="Gaussian MLE")
    ax.set(title="Distribution of daily net returns", xlabel="Daily return", ylabel="Density")
    ax.legend()
    return _save(fig, out_dir, "fig_distribution")


def fig_sensitivity(sens: dict[str, list[float]], out_dir: Path):
    style()
    fig, ax = plt.subplots(figsize=(WIDTH / 1.6, 3.2))
    ax.plot(sens["costs_bps"], sens["sharpe"], "o-", color=C_STRAT)
    ax.set(title="Sharpe ratio vs. transaction costs", xlabel="Cost (bps per unit turnover)",
           ylabel="Annualised Sharpe")
    return _save(fig, out_dir, "fig_sensitivity")


def make_all(r: pd.Series, b: pd.Series, sens: dict[str, list[float]], out_dir: Path,
             bench_label: str = "Benchmark") -> list[Path]:
    labels = ("Strategy", bench_label)
    return [
        *fig_equity(r, b, out_dir, labels), *fig_drawdown(r, b, out_dir, labels),
        *fig_rolling_sharpe(r, b, out_dir, labels=labels), *fig_distribution(r, out_dir),
        *fig_sensitivity(sens, out_dir),
    ]
