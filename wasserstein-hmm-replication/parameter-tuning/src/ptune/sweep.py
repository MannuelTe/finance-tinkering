"""Run sweep tasks in parallel, resumably.

    python -m ptune.sweep oat|knn|joint [--workers 9]

Each task writes results/runs/<key>.csv (date, gross return, turnover, weights) and one line
in results/runs.jsonl (task, key, seconds, headline metrics under the replication's
convention). Finished tasks are skipped on rerun, so the sweep can be interrupted.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "results" / "runs"
LOG = ROOT / "results" / "runs.jsonl"

_PRICES: dict = {}


def _prices(assets: str = "repl"):
    if assets not in _PRICES:
        from .data import prices

        _PRICES[assets] = prices(assets)
    return _PRICES[assets]


def run_task(task: dict) -> dict:
    from wasserstein_hmm.backtest import metrics

    from . import engine
    from .grid import WINDOWS, config_for, key

    k = key(task)
    path = RUNS / f"{k}.csv"
    config, extra = config_for(task["params"])
    start, end = WINDOWS[task["window"]]
    config = replace(config, oos_start=start, oos_end=end,
                     random_seed=task["seed"] or config.random_seed)
    t0 = time.time()
    px = _prices(extra.pop("assets"))
    if task["kind"] == "hmm":
        bt = engine.run_hmm(px, config, **extra)
    else:
        bt = engine.run_knn(px, config, outcome=extra["outcome"])
    frame = bt.weights.add_prefix("w_")
    frame.insert(0, "turnover", bt.turnover)
    frame.insert(0, "gross", bt.gross_returns)
    frame.to_csv(path, index_label="date")
    m = metrics(bt.gross_returns, bt.turnover)
    return {"key": k, "task": task, "seconds": round(time.time() - t0, 1),
            "sharpe": m["sharpe"], "max_drawdown": m["max_drawdown"],
            "turnover": m["turnover"], "total_return": m["total_return"]}


def main() -> None:
    from . import grid

    parser = argparse.ArgumentParser()
    parser.add_argument("which", choices=["oat", "knn", "joint", "paper", "r4", "check"])
    parser.add_argument("--workers", type=int, default=9)
    args = parser.parse_args()
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS"):
        os.environ[var] = "1"
    RUNS.mkdir(parents=True, exist_ok=True)
    tasks = {"oat": grid.oat_tasks, "knn": grid.knn_tasks, "joint": grid.joint_tasks,
             "paper": grid.paper_tasks, "r4": grid.r4_tasks,
             "check": lambda: [{"kind": "hmm", "window": "oos", "seed": 7, "params": {},
                                "tag": "check"}]}[args.which]()
    todo = [t for t in tasks if not (RUNS / f"{grid.key(t)}.csv").exists()]
    print(f"{len(tasks)} tasks, {len(todo)} to run", flush=True)
    done = 0
    with ProcessPoolExecutor(args.workers) as pool, LOG.open("a") as log:
        futures = [pool.submit(run_task, t) for t in todo]
        for f in as_completed(futures):
            try:
                row = f.result()
            except Exception as e:  # keep the sweep going; record the failure
                print(f"FAILED: {e!r}", flush=True)
                continue
            log.write(json.dumps(row, default=str) + "\n")
            log.flush()
            done += 1
            if done % 10 == 0 or done == len(todo):
                print(f"{done}/{len(todo)} done", flush=True)


if __name__ == "__main__":
    main()
