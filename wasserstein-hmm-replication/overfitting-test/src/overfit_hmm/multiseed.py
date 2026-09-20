"""PURPOSE: repeat the baseline-vs-blocked backtest over many seeds, in parallel.
INPUTS: --seeds N (default 30). Seed changes both HMM initialization and the random block layout.
OUTPUTS: results/multiseed/seed_<s>.csv (daily gross returns + selected K, both methods).
"""

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import pandas as pd

from .config import ROOT, OverfitConfig

OUT = ROOT / "results" / "multiseed"


def run_seed(seed: int) -> int:
    from wasserstein_hmm.backtest import run_hmm
    from wasserstein_hmm.data import load_prices
    from wasserstein_hmm.models import select_order

    from .selection import select_order_blocked

    path = OUT / f"seed_{seed}.csv"
    if path.exists():
        return seed
    config = replace(OverfitConfig(), random_seed=seed)
    prices = load_prices(config)
    frame = pd.DataFrame()
    for name, selector in (("baseline", select_order), ("blocked", select_order_blocked)):
        bt, _ = run_hmm(prices, config, selector)
        frame[f"{name}_ret"] = bt.gross_returns
        frame[f"{name}_turnover"] = bt.turnover
        frame[f"{name}_k"] = bt.orders
    frame.to_csv(path, index_label="date")
    return seed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    os.environ["OMP_NUM_THREADS"] = "1"
    OUT.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(args.workers) as pool:
        for seed in pool.map(run_seed, range(1, args.seeds + 1)):
            print(f"seed {seed} done", flush=True)


if __name__ == "__main__":
    main()
