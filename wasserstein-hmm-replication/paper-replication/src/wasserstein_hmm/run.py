"""PURPOSE: run the complete replication and persist audit artifacts.
INPUTS: optional --refresh-data flag.
OUTPUTS: results JSON, daily CSV diagnostics, and figures.
"""

from __future__ import annotations

import argparse
import json

from .backtest import metrics, passive_returns, run_hmm, run_knn
from .config import ASSET_LABELS, PUBLISHED, ROOT, ReplicationConfig
from .data import load_prices
from .report import create_figures

RESULTS = ROOT / "results"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-data", action="store_true")
    args = parser.parse_args()
    config = ReplicationConfig()
    prices = load_prices(config, refresh=args.refresh_data)
    hmm, selections = run_hmm(prices, config)
    knn = run_knn(prices, config)
    passive = passive_returns(prices, config)
    reproduced = {
        "wasserstein_hmm": metrics(hmm.gross_returns, hmm.turnover),
        "wasserstein_hmm_net_5bps": metrics(hmm.net_returns, hmm.turnover),
        "knn": metrics(knn.gross_returns, knn.turnover),
        "knn_net_5bps": metrics(knn.net_returns, knn.turnover),
        **{name: metrics(series) for name, series in passive.items()},
    }
    deltas = {
        method: {
            metric: reproduced[method][metric] - target
            for metric, target in targets.items() if metric in reproduced[method]
        }
        for method, targets in PUBLISHED.items()
    }
    result = {
        "paper": {"title": "Explainable Regime Aware Investing", "arxiv": "2603.04441v1"},
        "status": "method_reproduced_numerical_claims_not_independently_reproducible",
        "config": config.as_dict(),
        "asset_mapping": ASSET_LABELS,
        "sample": {
            "price_start": str(prices.index[0].date()), "price_end": str(prices.index[-1].date()),
            "oos_start": str(hmm.gross_returns.index[0].date()),
            "oos_end": str(hmm.gross_returns.index[-1].date()), "oos_observations": len(hmm.gross_returns),
        },
        "published": PUBLISHED, "reproduced": reproduced, "difference_reproduced_minus_published": deltas,
        "model_order_selections": selections,
        "regime_days": hmm.regimes.value_counts().sort_index().to_dict(),
        "average_weights": {
            "wasserstein_hmm": hmm.weights.mean().to_dict(), "knn": knn.weights.mean().to_dict(),
        },
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "results.json").write_text(json.dumps(result, indent=2, default=float) + "\n")
    diagnostics = hmm.weights.add_prefix("weight_")
    diagnostics["gross_return"] = hmm.gross_returns
    diagnostics["net_return"] = hmm.net_returns
    diagnostics["turnover"] = hmm.turnover
    diagnostics["regime"] = hmm.regimes
    diagnostics["hmm_order"] = hmm.orders
    diagnostics.to_csv(RESULTS / "hmm_daily.csv", index_label="date")
    knn.weights.add_prefix("weight_").assign(
        gross_return=knn.gross_returns, net_return=knn.net_returns, turnover=knn.turnover,
    ).to_csv(RESULTS / "knn_daily.csv", index_label="date")
    create_figures(ROOT, hmm, knn, passive, PUBLISHED, reproduced)
    print(json.dumps(reproduced, indent=2))


if __name__ == "__main__":
    main()

