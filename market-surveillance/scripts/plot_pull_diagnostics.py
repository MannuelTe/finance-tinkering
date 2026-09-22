"""Plot aggregate completeness diagnostics for a wide Bloomberg datapull.

    uv run python scripts/plot_pull_diagnostics.py data/raw/datapull_1.csv figures/pull1-diagnostic.png

Two panels: how many of the 433 offset-days each row filled (log scale, since a broken pull
is dominated by zero-observation rows), and the zero-return rate by deal type. Both are
aggregate counts only - no ticker, name or price appears in the plot or its data - so the
output is safe to commit even though the input under data/raw/ is not (see .gitignore).
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# Work even when the editable install's .pth file is skipped (macOS "hidden" flag on Python 3.13).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marketsurv.data.datapull import MIN_OBS

META_COLS = ["Deal Type", "Announce Date", "Target Name", "Acquirer Name", "Seller Name",
             "Announced Total Value (mil.)", "Payment Type", "TV/EBITDA", "Deal Status",
             "Target Ticker", "Acquirer Ticker", "Seller Ticker"]
BUCKET_FLOORS = [0, 1, 50, 100, 200, 300, MIN_OBS]  # last bucket ("usable") runs to n_days
RED, GREEN, GREY = "#d03b3b", "#0ca30c", "#8a97a1"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5,
    "axes.edgecolor": "#4c5a64", "axes.labelcolor": "#10171d",
    "text.color": "#10171d", "xtick.color": "#4c5a64", "ytick.color": "#4c5a64",
    "axes.spines.top": False, "axes.spines.right": False,
})


def plot(path: str, out: str) -> None:
    df = pd.read_csv(path, low_memory=False)
    offset_cols = [c for c in df.columns if c not in META_COLS]
    if not offset_cols:
        raise ValueError(f"no offset columns found in {path} (unexpected column layout)")
    body = df[offset_cols].apply(pd.to_numeric, errors="coerce").to_numpy()
    obs = np.isfinite(body).sum(axis=1)
    n_days = len(offset_cols)

    edges = [*BUCKET_FLOORS, n_days + 1]
    bucket_labels = ["0", "1-49", "50-99", "100-199", "200-299", "300-399", f"{MIN_OBS}-{n_days}"]
    counts = (pd.cut(obs, bins=edges, labels=bucket_labels, right=False, include_lowest=True)
              .value_counts().reindex(bucket_labels).fillna(0).astype(int))
    zero_rate_overall = (obs == 0).mean() * 100

    deal_order = df["Deal Type"].value_counts().index[::-1]
    rate_by_type = df.groupby("Deal Type").apply(lambda g: (obs[g.index] == 0).mean() * 100).reindex(deal_order)
    n_by_type = df["Deal Type"].value_counts().reindex(deal_order)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor="#f4f6f7")
    fig.suptitle("Completeness diagnostic", fontsize=15, fontweight="bold", x=0.02, ha="left")
    fig.text(0.02, 0.90, f"{len(df):,} rows pulled — {zero_rate_overall:.1f}% returned zero "
              "price observations", fontsize=10.5, color="#4c5a64", ha="left")

    ax = axes[0]
    ax.set_facecolor("#f4f6f7")
    colors = [RED] + [GREY] * (len(bucket_labels) - 2) + [GREEN]
    bars = ax.bar(bucket_labels, counts.values, color=colors, width=0.65)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylabel("rows (log scale)")
    ax.set_xlabel(f"price-days filled, out of {n_days}")
    ax.set_title("Completeness, by row", fontsize=11.5, loc="left")
    for b, v in zip(bars, counts.values):
        ax.annotate(f"{v:,}", (b.get_x() + b.get_width() / 2, v), textcoords="offset points",
                    xytext=(0, 3), ha="center", fontsize=9)
    ax.set_xticks(range(len(bucket_labels)))
    ax.set_xticklabels(bucket_labels, ha="right", rotation=30, fontsize=9)
    ax.yaxis.set_major_formatter(mticker.ScalarFormatter())

    ax = axes[1]
    ax.set_facecolor("#f4f6f7")
    bars = ax.barh(deal_order, rate_by_type.values, color=RED, height=0.6)
    ax.set_xlim(0, 108)
    ax.set_xlabel("zero-return rate (%)")
    ax.set_title("Zero-return rate, by deal type", fontsize=11.5, loc="left")
    for b, v, n in zip(bars, rate_by_type.values, n_by_type.values):
        ax.annotate(f"{v:.1f}%  (n={n:,})", (v, b.get_y() + b.get_height() / 2),
                    textcoords="offset points", xytext=(5, 0), va="center", fontsize=9)

    fig.text(0.02, 0.01, "Aggregate counts only — vendor rows are git-ignored per the "
              "Bloomberg redistribution terms.", fontsize=8.5, color="#7c8a93", ha="left")
    fig.tight_layout(rect=[0, 0.04, 1, 0.86])

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, facecolor=fig.get_facecolor())
    print(f"wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: plot_pull_diagnostics.py <datapull.csv> <out.png>")
    plot(sys.argv[1], sys.argv[2])
