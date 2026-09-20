"""PURPOSE: backtest the Wasserstein-HMM from 2019 with blocked vs. last-126-day order selection.
INPUTS: cached prices from the paper replication.
OUTPUTS: results/results.json, results/hmm_{blocked,baseline}_daily.csv, results/orders.png.
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from wasserstein_hmm.backtest import metrics, run_hmm  # noqa: E402
from wasserstein_hmm.data import load_prices  # noqa: E402
from wasserstein_hmm.models import select_order  # noqa: E402

from .config import ROOT, OverfitConfig  # noqa: E402
from .selection import select_order_blocked  # noqa: E402

RESULTS = ROOT / "results"


def main() -> None:
    config = OverfitConfig()
    prices = load_prices(config)
    runs = {
        "baseline_last126": run_hmm(prices, config, select_order),
        "blocked_cv": run_hmm(prices, config, select_order_blocked),
    }
    RESULTS.mkdir(exist_ok=True)
    summary = {"config": config.as_dict(), "methods": {}}
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    for name, (bt, selections) in runs.items():
        summary["methods"][name] = {
            "gross": metrics(bt.gross_returns, bt.turnover),
            "net_5bps": metrics(bt.net_returns, bt.turnover),
            "orders_selected": {d: s["selected"] for d, s in selections.items()},
            "regime_days": bt.regimes.value_counts().sort_index().to_dict(),
        }
        bt.weights.add_prefix("weight_").assign(
            gross_return=bt.gross_returns, net_return=bt.net_returns,
            turnover=bt.turnover, regime=bt.regimes, hmm_order=bt.orders,
        ).to_csv(RESULTS / f"hmm_{name.split('_')[0]}_daily.csv", index_label="date")
        axes[0].plot((1 + bt.gross_returns).cumprod(), label=name)
        axes[1].step(bt.orders.index, bt.orders, where="post", label=name)
    axes[0].set_ylabel("growth of 1 (gross)")
    axes[1].set_ylabel("selected states K")
    for ax in axes:
        ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "orders.png", dpi=130)
    (RESULTS / "results.json").write_text(json.dumps(summary, indent=2, default=float) + "\n")
    print(json.dumps({k: v["gross"] for k, v in summary["methods"].items()}, indent=2))


if __name__ == "__main__":
    main()
