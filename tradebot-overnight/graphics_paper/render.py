"""Render the paper's figures from the exported CSVs.

Reads   graphics_paper/data/*.csv   (written by research/paper_export.py)
Writes  graphics_paper/figures/*.png and *.pdf

Needs only pandas, numpy and matplotlib, so it runs anywhere the CSVs are:

    uv run --group paper python graphics_paper/render.py
    python graphics_paper/render.py --data path/to/data --out path/to/figures --formats png pdf

Strategy and accounting are described in data/meta.json and in tradebot/paper.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files; no display needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

# Okabe-Ito: distinguishable for common colour-vision deficiencies and in greyscale print.
COLORS = {
    "vol_aware": "#0072B2",
    "binary_ev": "#56B4E9",
    "always": "#E69F00",
    "cash": "#7f7f7f",
    "blend_hold": "#009E73",
    "classic": "#CC79A7",
    "spy": "#D55E00",
}
LABELS = {
    "vol_aware": "Vol-aware overnight SPY + rest",
    "binary_ev": "Overnight SPY, binary EV rule",
    "always": "Overnight SPY every day",
    "cash": "SPY slice in cash + rest",
    "blend_hold": "Blend, SPY held continuously",
    "classic": "60/40 (SPY/TLT)",
    "spy": "SPY buy & hold",
}
TRADED, SKIPPED = "#0072B2", "#D55E00"
FULL_WIDTH = 7.2


def style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 220,
            "font.family": "serif",
            "font.serif": ["DejaVu Serif", "Times New Roman", "Times"],
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#dddddd",
            "grid.linewidth": 0.6,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "figure.constrained_layout.use": True,
        }
    )


# --------------------------------------------------------------------------- data


def load(data: Path) -> dict:
    def read(name: str, **kw) -> pd.DataFrame:
        path = data / f"{name}.csv"
        if not path.exists():
            raise SystemExit(f"missing {path}: run research/paper_export.py first")
        return pd.read_csv(path, **kw)

    d = {
        "equity": read("equity", parse_dates=["date"]).set_index("date"),
        "returns": read("returns", parse_dates=["date"]).set_index("date"),
        "summary": read("summary"),
        "decisions": read("decisions", parse_dates=["decision_date", "sale_date"]),
        "sens_w": read("sensitivity_min_weight"),
        "sens_c": read("sensitivity_cost"),
        "window": read("window").iloc[0],
    }
    meta = data / "meta.json"
    d["meta"] = json.loads(meta.read_text()) if meta.exists() else {}
    dec = d["decisions"]
    dec["traded"] = dec["traded"].astype(bool)
    dec["intraday_missing"] = dec["intraday_missing"].astype(bool)
    return d


def subtitle(d: dict) -> str:
    w = d["window"]
    return f"{w['start']} to {w['end']}  |  {int(w['sessions'])} sessions  |  cost {w['cost_bps_roundtrip']:g} bps round trip"


def pct(ax, axis="y", decimals=0) -> None:
    fmt = matplotlib.ticker.PercentFormatter(1.0, decimals=decimals)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


# --------------------------------------------------------------------------- figures


def fig_equity(d: dict):
    eq = d["equity"]
    fig, ax = plt.subplots(figsize=(FULL_WIDTH, 4.0))
    order = ["spy", "classic", "blend_hold", "cash", "always", "binary_ev", "vol_aware"]
    for key in order:
        strong = key == "vol_aware"
        ax.plot(eq.index, eq[key], color=COLORS[key], lw=2.2 if strong else 1.1,
                alpha=1.0 if strong else 0.85, label=LABELS[key], zorder=3 if strong else 2)
    ax.set_yscale("log")
    ax.set_yticks([80, 100, 125, 150, 200, 250])
    ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.minorticks_off()
    ax.set_ylabel("Portfolio value (start = 100, log scale)")
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.set_title("Cumulative performance of the whole portfolio", pad=18)
    ax.text(0, 1.015, subtitle(d), transform=ax.transAxes, va="bottom", fontsize=7.5, color="#555555")
    # End-of-line value labels, nudged apart (in log space) so neighbours never overprint.
    ax.set_xlim(right=eq.index[-1] + pd.Timedelta(days=60))
    last = eq.iloc[-1].sort_values()
    placed, gap = [], 0.05
    for key, value in last.items():
        y = np.log(value)
        if placed and y - placed[-1][1] < gap:
            y = placed[-1][1] + gap
        placed.append((key, y))
    for key, y in placed:
        ax.text(eq.index[-1] + pd.Timedelta(days=8), float(np.exp(y)), f"{last[key]:.0f}",
                fontsize=7.5, color=COLORS[key], va="center", fontweight="bold")
    ax.legend(loc="upper left", ncol=2)
    return fig


def fig_drawdown(d: dict):
    r = d["returns"]
    fig, ax = plt.subplots(figsize=(FULL_WIDTH, 3.1))
    for key in ["spy", "blend_hold", "cash", "vol_aware"]:
        wealth = (1 + r[key]).cumprod()
        dd = wealth / wealth.cummax() - 1
        if key == "spy":  # one shaded area only: overlapping fills turn into mud
            ax.fill_between(dd.index, dd, 0, color=COLORS[key], alpha=0.18, linewidth=0)
        ax.plot(dd.index, dd, color=COLORS[key], lw=1.9 if key == "vol_aware" else 0.9, label=LABELS[key])
    pct(ax)
    ax.set_ylabel("Drawdown from previous peak")
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.set_title("Drawdowns")
    ax.legend(loc="lower left", ncol=2)
    return fig


def fig_rolling_sharpe(d: dict):
    """Rolling six-month annualized Sharpe ratio, using a zero risk-free rate.

    The window is 126 sessions and the standard deviation uses the sample divisor, matching the
    convention in the general backtest metrics. A rolling estimate is descriptive and unstable;
    it is deliberately shown for only the four principal comparators.
    """
    r = d["returns"]
    window = 126
    fig, ax = plt.subplots(figsize=(FULL_WIDTH, 3.25))
    for key in ["spy", "classic", "blend_hold", "vol_aware"]:
        rolling = r[key].rolling(window, min_periods=window)
        sharpe = np.sqrt(252) * rolling.mean() / rolling.std(ddof=1)
        ax.plot(
            sharpe.index,
            sharpe,
            color=COLORS[key],
            lw=2.0 if key == "vol_aware" else 1.0,
            label=LABELS[key],
        )
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("Annualized Sharpe ratio")
    ax.set_title("Rolling 126-session Sharpe ratio (risk-free rate = 0)")
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.legend(loc="upper left", ncol=2)
    return fig


def fig_sharpe_difference(d: dict):
    """Histogram of paired rolling Sharpe differences: volatility-aware minus SPY."""
    r = d["returns"]
    window = 126

    def rolling_sharpe(key: str) -> pd.Series:
        rolling = r[key].rolling(window, min_periods=window)
        return np.sqrt(252) * rolling.mean() / rolling.std(ddof=1)

    difference = (rolling_sharpe("vol_aware") - rolling_sharpe("spy")).dropna()
    mean = float(difference.mean())
    median = float(difference.median())

    fig, ax = plt.subplots(figsize=(FULL_WIDTH * 0.78, 3.2))
    ax.hist(difference, bins=24, color=COLORS["vol_aware"], alpha=0.78, edgecolor="white")
    ax.axvline(0, color="black", lw=1.0, label="Equal rolling Sharpe")
    ax.axvline(mean, color=COLORS["spy"], lw=1.5, ls="--", label=f"Mean: {mean:+.2f}")
    ax.axvline(median, color=COLORS["classic"], lw=1.5, ls=":", label=f"Median: {median:+.2f}")
    ax.set_xlabel("Rolling Sharpe difference (vol-aware minus SPY buy & hold)")
    ax.set_ylabel("Overlapping 126-session windows")
    ax.set_title("Distribution of rolling Sharpe differences")
    ax.legend(loc="upper left")
    return fig


def fig_slice_contribution(d: dict):
    """What the SPY-slice rule adds on top of leaving that slice in cash."""
    r = d["returns"]
    fig, ax = plt.subplots(figsize=(FULL_WIDTH, 3.0))
    for key in ["always", "binary_ev", "vol_aware"]:
        extra = (1 + r[key]).cumprod() / (1 + r["cash"]).cumprod() - 1
        ax.plot(extra.index, extra, color=COLORS[key], lw=2.0 if key == "vol_aware" else 1.2, label=LABELS[key])
    ax.axhline(0, color="black", lw=0.8)
    pct(ax, decimals=1)
    ax.set_ylabel("Cumulative gain vs. keeping\nthe SPY slice in cash")
    ax.set_title("Contribution of the overnight SPY rules")
    ax.legend(loc="upper left")
    return fig


def fig_decisions(d: dict):
    dec = d["decisions"]
    dec = dec[~dec["intraday_missing"]].sort_values("decision_date")
    fig, (top, bot) = plt.subplots(2, 1, figsize=(FULL_WIDTH, 5.0), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1.4]})
    vol = dec["sigma_intraday"] * 100
    top.plot(dec["decision_date"], vol, color="#bbbbbb", lw=0.7, zorder=1)
    for flag, color, name in [(True, TRADED, "Held overnight"), (False, SKIPPED, "SPY untouched")]:
        sub = dec[dec["traded"] == flag]
        top.scatter(sub["decision_date"], sub["sigma_intraday"] * 100, s=7, color=color, label=f"{name} ({len(sub)})", zorder=2)
    top.set_ylabel("Intraday volatility to 15:00\n(daily-equivalent, %)")
    top.set_title("Daily decisions and the volatility they were based on")
    top.legend(loc="upper right", ncol=2, markerscale=1.6)
    frac = dec.set_index("decision_date")["traded"].astype(float).rolling(60, min_periods=30).mean()
    bot.plot(frac.index, frac, color=TRADED, lw=1.5)
    bot.set_ylim(0, 1.02)
    pct(bot)
    bot.set_ylabel("Share of days held\n(rolling 60)")
    bot.xaxis.set_major_formatter(mdates.ConciseDateFormatter(bot.xaxis.get_major_locator()))
    return fig


def fig_vol_vs_overnight(d: dict):
    dec = d["decisions"]
    dec = dec[~dec["intraday_missing"]].dropna(subset=["sigma_intraday", "next_overnight_return"])
    x, y = dec["sigma_intraday"] * 100, dec["next_overnight_return"] * 100
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL_WIDTH, 3.5), gridspec_kw={"width_ratios": [1.5, 1]})
    for flag, color, name in [(True, TRADED, "held"), (False, SKIPPED, "skipped")]:
        m = dec["traded"] == flag
        a.scatter(x[m], y[m], s=8, alpha=0.55, color=color, label=f"{name} ({int(m.sum())})", linewidths=0)
    a.axhline(0, color="black", lw=0.7)
    a.set_xlabel("Intraday volatility to 15:00 (daily-equivalent, %)")
    a.set_ylabel("Next overnight return (%)")
    a.set_title("Does morning volatility say anything about the night?")
    a.legend(loc="lower right", markerscale=1.8)
    bins = pd.qcut(x, 5, duplicates="drop")
    grouped = pd.DataFrame({"y": y, "x": x}).groupby(bins, observed=True).agg(y=("y", "mean"), n=("y", "size"),
                                                                            se=("y", lambda s: s.std(ddof=1) / np.sqrt(len(s))))
    b.bar(range(len(grouped)), grouped["y"], yerr=1.96 * grouped["se"], color="#56B4E9", capsize=3, edgecolor="none")
    b.axhline(0, color="black", lw=0.7)
    b.set_xticks(range(len(grouped)))
    b.set_xticklabels(["calm", "2", "3", "4", "stormy"][: len(grouped)])
    b.set_xlabel("Volatility quintile")
    b.set_ylabel("Mean overnight return (%), 95% CI")
    b.set_title("By quintile")
    return fig


def fig_distributions(d: dict):
    dec = d["decisions"]
    dec = dec[~dec["intraday_missing"]].dropna(subset=["next_overnight_return"])
    fig, ax = plt.subplots(figsize=(FULL_WIDTH * 0.75, 3.4))
    lim = float(np.nanpercentile(np.abs(dec["next_overnight_return"] * 100), 99))
    edges = np.linspace(-lim, lim, 45)
    outside = 0
    for flag, color, name in [(True, TRADED, "Held overnight"), (False, SKIPPED, "SPY untouched")]:
        vals = dec.loc[dec["traded"] == flag, "next_overnight_return"] * 100
        outside += int((vals.abs() > lim).sum())
        ax.hist(vals[vals.abs() <= lim], bins=edges, color=color, alpha=0.55, density=True,
                label=f"{name}: n={len(vals)}, mean {vals.mean():+.3f}%, sd {vals.std():.2f}%")
        ax.axvline(vals.mean(), color=color, lw=1.4, ls="--")
    ax.axvline(0, color="black", lw=0.7)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.4)  # headroom so the legend clears the tallest bars
    ax.set_xlabel("Next overnight return (%): the return the rule chose to take or avoid")
    ax.set_ylabel("Density")
    ax.set_title("What the rule held and what it skipped")
    ax.legend(loc="upper right")
    ax.text(0.01, 0.98, f"{outside} days beyond \u00b1{lim:.1f}% not shown", transform=ax.transAxes,
            ha="left", va="top", fontsize=7, color="#555555")
    return fig


def fig_sensitivity(d: dict):
    """Both panels share the same Sharpe and CAGR axes, so flat really looks flat and a real
    effect (trading cost) looks like one."""
    fig, axes = plt.subplots(1, 2, figsize=(FULL_WIDTH, 3.5), sharey=True)
    for ax, key, xcol, title, xlabel in [
        (axes[0], "sens_w", "min_weight", "Minimum-weight bar (0 = any positive edge)",
         "Minimum sized weight to trade\n(share of days held shown under each value)"),
        (axes[1], "sens_c", "cost_bps", "Round-trip trading cost", "Round-trip cost (bps)"),
    ]:
        s = d[key]
        ax.plot(s[xcol], s["sharpe"], "o-", color=COLORS["vol_aware"], label="Sharpe (left)")
        ax.set_ylim(1.0, 2.0)
        ax.set_xlabel(xlabel)
        ax.set_title(title)
        twin = ax.twinx()
        twin.grid(False)
        twin.spines["right"].set_visible(True)
        twin.plot(s[xcol], s["cagr"], "s--", color=COLORS["spy"], label="CAGR (right)")
        twin.set_ylim(0.06, 0.24)
        twin.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        if key == "sens_w":
            ax.set_xticks(s[xcol])
            ax.set_xticklabels([f"{v:g}\n{f:.0%}" for v, f in zip(s[xcol], s["trade_fraction"], strict=True)],
                               fontsize=7.5)
        lines = ax.get_lines() + twin.get_lines()
        ax.legend(lines, [ln.get_label() for ln in lines], loc="lower left")
        if ax is axes[0]:
            ax.set_ylabel("Sharpe ratio")
        else:
            twin.set_ylabel("CAGR")
    return fig


def fig_summary_table(d: dict):
    s = d["summary"].copy()
    rows = []
    for _, r in s.iterrows():
        rows.append([r["strategy"], f"{r['total_return']:.1%}", f"{r['cagr']:.1%}", f"{r['volatility']:.1%}",
                     f"{r['sharpe']:.2f}", f"{r['max_drawdown']:.1%}"])
    fig, ax = plt.subplots(figsize=(FULL_WIDTH, 0.5 + 0.34 * len(rows)))
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=["Strategy", "Total", "CAGR", "Volatility", "Sharpe", "Max DD"],
                     loc="center", cellLoc="right", colLoc="right")
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 1.35)
    table.auto_set_column_width(range(6))
    for cell in table.get_celld().values():
        cell.PAD = 0.06
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if col == 0:
            cell.set_text_props(ha="left")
            cell._loc = "left"
        if row == 0:
            cell.set_facecolor("#eeeeee")
            cell.set_text_props(weight="bold")
        elif rows[row - 1][0] == LABELS["vol_aware"]:
            cell.set_facecolor("#e6f1f8")
    ax.set_title("Summary statistics (daily returns, risk-free rate 0)", loc="left")
    return fig


FIGURES = {
    "fig1_equity": fig_equity,
    "fig2_drawdown": fig_drawdown,
    "fig9_rolling_sharpe": fig_rolling_sharpe,
    "fig10_sharpe_difference": fig_sharpe_difference,
    "fig3_slice_contribution": fig_slice_contribution,
    "fig4_decisions": fig_decisions,
    "fig5_vol_vs_overnight": fig_vol_vs_overnight,
    "fig6_distributions": fig_distributions,
    "fig7_sensitivity": fig_sensitivity,
    "fig8_summary_table": fig_summary_table,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=HERE / "data")
    parser.add_argument("--out", type=Path, default=HERE / "figures")
    parser.add_argument("--formats", nargs="+", default=["png", "pdf"])
    args = parser.parse_args()

    style()
    d = load(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, make in FIGURES.items():
        fig = make(d)
        for ext in args.formats:
            fig.savefig(args.out / f"{name}.{ext}")
        plt.close(fig)
        print(f"wrote {name}")
    print(f"figures in {args.out}")


if __name__ == "__main__":
    main()
