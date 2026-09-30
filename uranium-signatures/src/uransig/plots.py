"""Signature figure: mean signed CAR path of bull vs sign-flipped bear events."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MultipleLocator, PercentFormatter

# Reference palette (light mode), same as TaxHarvest: categorical slots 1-2, ink, chrome.
BLUE, ORANGE = "#2a78d6", "#eb6834"
BLUE_LIGHT = "#9ec5f4"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 9, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False,
        "axes.spines.right": False, "legend.frameon": False, "legend.fontsize": 8,
        "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "text.color": INK, "lines.linewidth": 2,
    })


def _band(ar: pd.DataFrame, n_boot=2000, seed=0):
    """Mean CAR path and a 90% bootstrap band over events."""
    rng = np.random.default_rng(seed)
    a = ar.to_numpy()
    boots = np.array([a[rng.integers(0, len(a), len(a))].mean(0).cumsum() for _ in range(n_boot)])
    return a.mean(0).cumsum(), np.percentile(boots, 5, 0), np.percentile(boots, 95, 0)


def signatures(bull: pd.DataFrame, bear: pd.DataFrame, out: Path, title: str):
    style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"width_ratios": [3, 2]})
    days = bull.columns.to_numpy()
    for ar, color, lab in ((bull, BLUE, f"Bullish news (n={len(bull)})"),
                           (bear, ORANGE, f"Bearish news, sign flipped (n={len(bear)})")):
        m, lo, hi = _band(ar)
        a.fill_between(days, lo, hi, color=color, alpha=0.15, lw=0)
        a.plot(days, m, color=color, label=lab)
        a.annotate(f"{m[-1]:+.0%}", (days[-1], m[-1]), xytext=(4, 0),
                   textcoords="offset points", va="center", fontsize=8, color=INK2)
        # right panel: the same path scaled by its day +20 value, first 20 days only
        k = days <= 20
        scale = m[days == 20][0] - m[days == -1][0]
        b.plot(days[k], (m[k] - m[days == -1][0]) / scale, color=color)
    a.axvline(0, color=AXIS, lw=1)
    a.axhline(0, color=AXIS, lw=1)
    a.set_title(title)
    a.set_xlabel("Trading days from the news")
    a.set_ylabel("Mean abnormal return, in the news direction")
    a.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    a.legend(loc="upper left")
    b.axvline(0, color=AXIS, lw=1)
    b.axhline(1, color=AXIS, lw=1, ls=":")
    b.set_title("How fast: share of the day +20 move")
    b.set_xlabel("Trading days from the news")
    b.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def adjustment(fits: dict, paths: dict, out: Path):
    """Mean CAR from day 0 with the fitted partial-adjustment curve and its half-life."""
    style()
    fig, ax = plt.subplots(figsize=(7, 4))
    for (name, fit), color in zip(fits.items(), (BLUE, ORANGE)):
        car = paths[name]
        t = np.arange(len(car))
        g = fit["A"] * (1 - (1 - fit["kappa"]) ** (t + 1))
        ax.plot(t, car, color=color, lw=0, marker="o", ms=4, alpha=0.7)
        lo, hi = fit["hl_ci"]
        ax.plot(t, g, color=color, label=f"{name}: half-life {fit['half_life']:.1f} days "
                f"(90% CI {lo:.1f}–{min(hi, 60):.0f}{'+' if hi > 60 else ''})")
        h = fit["half_life"]
        ax.plot([h, h], [0, fit["A"] / 2], color=color, lw=1, ls=":")
    ax.axhline(0, color=AXIS, lw=1)
    ax.set_title("Partial adjustment: how fast each kind of news is priced")
    ax.set_xlabel("Trading days from the news (day 0 = first session it could trade)")
    ax.set_ylabel("Mean abnormal return, in the news direction")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def lead_lag(panels: list[tuple[str, pd.Series, int, str]], out: Path):
    """Cross-correlation bars; one panel per (title, series, n, x-label)."""
    style()
    fig, axes = plt.subplots(1, len(panels), figsize=(4.2 * len(panels), 3.6), sharey=True)
    for ax, (title, cc, n, xlab) in zip(np.atleast_1d(axes), panels):
        ax.bar(cc.index, cc.values, color=[BLUE if k == 0 else BLUE_LIGHT for k in cc.index],
               width=0.7)
        band = 2 / np.sqrt(n)
        for y in (band, -band):
            ax.axhline(y, color=MUTED, lw=1, ls="--")
        ax.axhline(0, color=AXIS, lw=1)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel(xlab)
        ax.set_xticks(cc.index)
    np.atleast_1d(axes)[0].set_ylabel("Correlation")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def backtest(t: pd.DataFrame, baseline: np.ndarray, out: Path):
    """Left: cumulative net P&L of taken trades. Right: actual mean vs random trades."""
    style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw={"width_ratios": [3, 2]})
    tk = t[t.taken].copy()
    tk["day0"] = pd.to_datetime(tk["day0"])
    tk = tk.sort_values("day0")
    a.step(tk["day0"], tk["net"].cumsum(), where="post", color=INK2, lw=1.5)
    for d, color, lab in (("bull", BLUE, "long after bullish news"),
                          ("bear", ORANGE, "short after bearish news")):
        s = tk[tk.direction == d]
        a.scatter(s["day0"], tk["net"].cumsum()[s.index], color=color, s=28, zorder=3,
                  edgecolor=SURFACE, lw=1, label=lab)
    a.axhline(0, color=AXIS, lw=1)
    a.set_title("Walk-forward: sum of net trade returns")
    a.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    a.legend(loc="upper left")
    m = tk["net"].mean()
    b.hist(baseline, bins=40, color=BLUE_LIGHT, edgecolor=SURFACE)
    b.axvline(m, color=INK, lw=2)
    p = (baseline >= m).mean()
    b.annotate(f"strategy {m:+.1%}\nrandom ≥ this: {p:.0%}", (m, b.get_ylim()[1] * 0.9),
               xytext=(6, 0), textcoords="offset points", fontsize=8, color=INK2, va="top")
    b.set_title(f"Mean net per trade vs {len(baseline):,} random books")
    b.xaxis.set_major_locator(MultipleLocator(0.02))
    b.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    b.set_yticks([])
    b.spines["left"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
