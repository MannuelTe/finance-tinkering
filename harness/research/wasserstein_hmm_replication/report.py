"""PURPOSE: produce replication figures plus concise Markdown and PDF audit reports.
INPUTS: backtests, published targets, reproduced metrics, and resolved configuration.
OUTPUTS: PNG figures, REPLICATION_REPORT.md, and output/pdf report.
"""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .backtest import Backtest


def _wealth(returns: pd.Series) -> pd.Series:
    return (1 + returns).cumprod()


def create_figures(
    directory: Path,
    hmm: Backtest,
    knn: Backtest,
    passive: dict[str, pd.Series],
    published: dict[str, dict[str, float]],
    reproduced: dict[str, dict[str, float]],
) -> list[Path]:
    out = directory / "figures"
    out.mkdir(exist_ok=True)
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

    fig, axes = plt.subplots(2, 1, figsize=(8.0, 6.0), sharex=True)
    hmm.weights.plot.area(ax=axes[0], stacked=True, linewidth=0)
    axes[0].set(title="Wasserstein-HMM portfolio weights", ylabel="Weight", ylim=(0, 1))
    axes[0].legend(ncol=5, fontsize=8, loc="upper center")
    axes[1].plot(hmm.turnover, label="HMM", lw=0.9)
    axes[1].plot(knn.turnover, label="KNN", lw=0.6, alpha=0.7)
    axes[1].set(title="Daily one-way turnover", ylabel="Turnover")
    axes[1].legend()
    path = out / "weights_and_turnover.png"
    fig.tight_layout(); fig.savefig(path, dpi=220); plt.close(fig); paths.append(path)

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


def _metric_table(result: dict[str, Any]) -> list[list[str]]:
    rows = [["Method", "Sharpe pub/rep", "Max DD pub/rep", "Turnover pub/rep"]]
    names = {"wasserstein_hmm": "Wasserstein HMM", "knn": "KNN", "equal_weight": "Equal weight", "spx": "SPX"}
    for key, name in names.items():
        pub, rep = result["published"][key], result["reproduced"][key]
        rows.append([
            name,
            f"{pub['sharpe']:.2f} / {rep['sharpe']:.2f}",
            f"{100 * pub['max_drawdown']:.2f}% / {100 * rep['max_drawdown']:.2f}%",
            "-" if "turnover" not in pub else f"{pub['turnover']:.4f} / {rep['turnover']:.4f}",
        ])
    return rows


def write_markdown(directory: Path, result: dict[str, Any]) -> Path:
    rows = _metric_table(result)
    table = "\n".join(["| " + " | ".join(row) + " |" for row in rows[:1]] +
                      ["|---|---:|---:|---:|"] +
                      ["| " + " | ".join(row) + " |" for row in rows[1:]])
    config = result["config"]
    text = f"""# Clean-room replication: Explainable Regime Aware Investing

## Verdict

The paper's architecture was reproduced, but its numerical claims are not independently reproducible from the publication. The arXiv bundle contains no implementation or data snapshot, labels its reported model "Commercial V2.0," and omits the exact tickers, test split, HMM settings, feature scaling, template initialization, optimizer coefficients, and realized-cost convention.

{table}

## What was reproduced

- Strictly lagged return, 60-session volatility, and 20-session momentum features.
- Expanding-window Gaussian HMM with predictive model-order selection.
- Six persistent templates matched with closed-form Gaussian 2-Wasserstein distance.
- Template-probability-weighted conditional return moments.
- Long-only, capped, transaction-penalized mean-variance allocation.
- An expanding KNN conditional-moment baseline using the same optimizer.

## Explicit assumptions

- Yahoo adjusted-close ETFs: SPY, TLT, GLD, USO, and UUP.
- OOS: {config['oos_start']} through {config['oos_end']} ({result['sample']['oos_observations']} observations).
- HMM candidates {config['candidate_states']}; six templates; refit every {config['refit_frequency']} sessions; order selection every {config['order_selection_frequency']} sessions.
- Risk aversion {config['risk_aversion']}, turnover penalty {config['turnover_penalty']}, maximum weight {config['max_weight']:.0%}; reported primary results are gross, with a separate 5-bp realized-cost result in `results.json`.

## Why an exact match fails

1. The empirical specification is underdetermined: changing any omitted ticker, scaling, covariance type, refit cadence, or penalty changes the result materially.
2. The paper's own source contains an older result table and a newer "Commercial V2.0" table while reusing figure files.
3. Its timing notation is inconsistent: features include `r_t`, all features are said to stop at `t-1`, and the pseudocode realizes `w_t' r_t`.
4. Its HMM Gaussian means/covariances are 15-dimensional feature moments, yet the displayed portfolio equation uses them as five-asset return moments without specifying the projection.
5. Published SPX benchmark statistics do not match the disclosed Yahoo adjusted-close window under standard Sharpe/drawdown definitions.

This is a research reproduction, not investment advice or evidence of future returns.
"""
    path = directory / "REPLICATION_REPORT.md"
    path.write_text(text)
    return path


def write_pdf(directory: Path, result: dict[str, Any], figures: list[Path]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "explainable_regime_investing_replication.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(path), pagesize=letter, rightMargin=48, leftMargin=48, topMargin=46, bottomMargin=46,
        title="Clean-room replication: Explainable Regime Aware Investing",
        author="Harness Research",
        subject="Reproducibility audit of arXiv:2603.04441v1",
    )
    story = [
        Paragraph("Clean-room replication: Explainable Regime Aware Investing", styles["Title"]),
        Paragraph("Boukardagha (2026), arXiv:2603.04441v1", styles["Heading2"]),
        Spacer(1, 10),
        Paragraph("Verdict", styles["Heading1"]),
        Paragraph(
            "The disclosed architecture can be implemented, but the reported numerical claims cannot be independently reproduced from the paper. This report separates published targets from a causal implementation under explicit assumptions.",
            styles["BodyText"],
        ),
        Spacer(1, 10),
    ]
    table = Table(_metric_table(result), colWidths=[1.35 * inch, 1.25 * inch, 1.45 * inch, 1.45 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF3F8")]),
    ]))
    story += [table, Spacer(1, 12), Image(str(figures[2]), width=7 * inch, height=3.15 * inch), PageBreak()]
    story += [
        Paragraph("Implementation", styles["Heading1"]),
        Paragraph(
            "The reproduction uses strictly lagged features, expanding histories, a full-covariance Gaussian HMM, predictive order selection, six Wasserstein-tracked templates, template-conditioned asset-return moments, and a convex long-only mean-variance allocation with an exact L1 turnover epigraph.",
            styles["BodyText"],
        ),
        Spacer(1, 8), Image(str(figures[0]), width=7 * inch, height=3.75 * inch),
        Spacer(1, 8), Image(str(figures[1]), width=7 * inch, height=5.25 * inch), PageBreak(),
        Paragraph("Failure analysis", styles["Heading1"]),
    ]
    reasons = [
        "No code, data snapshot, or complete hyperparameter table is released.",
        "The arXiv source contains conflicting old and new numerical tables and calls the final model Commercial V2.0.",
        "Exact instruments and return conventions are undisclosed; labels such as SPX, BOND, OIL, and USD are not Yahoo tickers.",
        "The causal timing and the mapping from 15-dimensional HMM feature moments to five-asset portfolio moments are not fully specified.",
        "The benchmark statistics do not reconcile with standard calculations on the apparent Yahoo test window.",
    ]
    for i, reason in enumerate(reasons, 1):
        story.append(Paragraph(f"{i}. {reason}", styles["BodyText"]))
        story.append(Spacer(1, 5))
    story += [
        Spacer(1, 10), Paragraph("Conclusion", styles["Heading1"]),
        Paragraph(
            "This run is evidence that the method can be implemented causally, not verification of the paper's headline numbers. Differences are scientifically informative because the publication leaves enough degrees of freedom to generate materially different outcomes. This is not investment advice.",
            styles["BodyText"],
        ),
    ]
    doc.build(story)
    return path
