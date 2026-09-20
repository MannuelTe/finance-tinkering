"""PURPOSE: test whether a diversified bond sleeve changes the replication versus TLT alone.
INPUTS: cached SPY/GLD/USO/UUP/TLT prices plus extra bond ETFs (downloaded once and cached).
OUTPUTS: results/bond_extension.json and figures/bond_extension.png.
"""

from __future__ import annotations

import json
from dataclasses import replace

import matplotlib.pyplot as plt
import pandas as pd

from .backtest import metrics, passive_returns, run_hmm, run_knn
from .config import ROOT, ReplicationConfig
from .data import load_prices

EXTRA_BONDS = ("IEF", "LQD", "TIP")  # 7-10y Treasuries, investment-grade credit, TIPS
BOND_BASKET = ("TLT", *EXTRA_BONDS)
EXTRA_CACHE = ROOT / "data" / "bond_prices.csv"


def load_extra_bonds(config: ReplicationConfig) -> pd.DataFrame:
    if not EXTRA_CACHE.exists():
        import yfinance as yf

        raw = yf.download(
            list(EXTRA_BONDS), start=config.data_start, end=config.data_end_exclusive,
            auto_adjust=True, progress=False,
        )
        raw["Close"].to_csv(EXTRA_CACHE)
    extra = pd.read_csv(EXTRA_CACHE, index_col=0, parse_dates=True)
    extra.index = pd.DatetimeIndex(extra.index).tz_localize(None).rename("date")
    return extra


def build_variants(prices: pd.DataFrame, extra: pd.DataFrame) -> dict[str, pd.DataFrame]:
    joined = prices.join(extra, how="inner")
    equity_side = ["SPY", "GLD", "USO", "UUP"]
    composite = (1 + joined[list(BOND_BASKET)].pct_change().mean(axis=1)).cumprod()
    composite = composite.fillna(1.0).rename("BONDS")
    return {
        "tlt_only": joined[["SPY", "TLT", "GLD", "USO", "UUP"]],
        "bond_composite": joined[equity_side].join(composite)[["SPY", "BONDS", "GLD", "USO", "UUP"]],
        "bond_separate": joined[["SPY", *BOND_BASKET, "GLD", "USO", "UUP"]],
    }


def main() -> None:
    config = ReplicationConfig()
    variants = build_variants(load_prices(config), load_extra_bonds(config))
    results: dict[str, object] = {"bond_basket": list(BOND_BASKET), "variants": {}}
    curves: dict[str, pd.Series] = {}
    for name, panel in variants.items():
        cfg = replace(config, tickers=tuple(panel.columns))
        hmm, _ = run_hmm(panel, cfg)
        knn = run_knn(panel, cfg)
        passive = passive_returns(panel, cfg)
        results["variants"][name] = {
            "assets": list(panel.columns),
            "wasserstein_hmm": metrics(hmm.gross_returns, hmm.turnover),
            "wasserstein_hmm_net_5bps": metrics(hmm.net_returns, hmm.turnover),
            "knn": metrics(knn.gross_returns, knn.turnover),
            "equal_weight": metrics(passive["equal_weight"]),
            "average_weights_hmm": hmm.weights.mean().to_dict(),
        }
        curves[name] = (1 + hmm.gross_returns).cumprod()
        print(name, results["variants"][name]["wasserstein_hmm"], flush=True)
    (ROOT / "results" / "bond_extension.json").write_text(json.dumps(results, indent=2) + "\n")

    labels = {
        "tlt_only": "TLT only (baseline)",
        "bond_composite": "Bond composite (TLT, IEF, LQD, TIP)",
        "bond_separate": "Bonds as separate assets",
    }
    fig, ax = plt.subplots(figsize=(8.0, 4.3))
    for name, curve in curves.items():
        ax.plot(curve, label=labels[name], lw=1.3)
    ax.set(title="Wasserstein HMM: effect of a diversified bond sleeve", ylabel="Wealth")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "bond_extension.png", dpi=220)


if __name__ == "__main__":
    main()
