"""The pre-registered search space (see PLAN.md). Written before any sweep result was seen."""

from __future__ import annotations

import json
import random
from dataclasses import replace

from wasserstein_hmm.config import ReplicationConfig

# Windows: the paper's test window, and an earlier window used only for choosing settings.
WINDOWS = {
    "oos": ("2023-06-02", "2026-02-20"),
    "tune": ("2019-01-02", "2023-05-31"),
    # Amendment (paper_hints.md): the window that reconciles the paper's benchmarks.
    "paper_oos": ("2023-06-05", "2026-02-19"),
}
# Engine switches that are not ReplicationConfig fields, with the replication's defaults.
EXTRA_DEFAULTS = {"cov_type": "full", "mixture_cov": False, "outcome": "simple",
                  "regime_cov": "diag", "assets": "repl"}

# The replication's choices (the baseline) are the first value listed where relevant.
BASE = {**ReplicationConfig().as_dict(), "cov_type": "full", "mixture_cov": False}
BASE["candidate_states"] = tuple(BASE["candidate_states"])
BASE["tickers"] = tuple(BASE["tickers"])

# Unstated parameters and the values tried for each (one-at-a-time and joint sampling).
GRID: dict[str, list] = {
    "turnover_penalty": [0.0, 1e-4, 5e-4, 1e-3, 3e-3, 1e-2],
    "risk_aversion": [1.0, 2.0, 3.0, 5.0, 10.0],
    "max_weight": [0.4, 0.5, 0.6, 0.8, 1.0],
    "covariance_shrinkage": [0.0, 0.1, 0.3, 0.5],
    "template_smoothing": [0.01, 0.02, 0.05, 0.1, 0.2],
    "template_count": [3, 4, 6, 8],
    "refit_frequency": [5, 10, 21],
    "order_selection_frequency": [21, 63, 126],
    "validation_days": [63, 126, 252],
    "complexity_penalty": [0.0, 0.001, 0.002, 0.005],
    "candidate_states": [(2, 3, 4), (2, 3, 4, 5, 6), (3, 4, 5, 6)],
    "volatility_window": [20, 60, 120],
    "momentum_window": [10, 20, 60],
    "hmm_iterations": [25, 50, 100],
    "cov_type": ["full", "diag"],
    "mixture_cov": [False, True],
}
# KNN-only parameter; KNN also shares the optimizer and feature-window parameters.
KNN_GRID = {"knn_neighbors": [10, 25, 50, 100, 200]}
KNN_SHARED = ("turnover_penalty", "risk_aversion", "max_weight", "volatility_window",
              "momentum_window")

OAT_SEEDS = (1, 2, 3, 4, 5)
BASELINE_SEEDS = tuple(range(1, 21))
N_JOINT = 200
JOINT_SEED = 20260930


def config_for(params: dict) -> tuple[ReplicationConfig, dict]:
    """Split a parameter dict into a ReplicationConfig and the engine-only switches."""
    p = {**BASE, **params}
    extra = {k: p.pop(k, d) for k, d in EXTRA_DEFAULTS.items()}
    p["candidate_states"] = tuple(p["candidate_states"])
    p["tickers"] = tuple(p["tickers"])
    return replace(ReplicationConfig(), **p), extra


def key(task: dict) -> str:
    import hashlib

    return hashlib.sha1(json.dumps(task, sort_keys=True, default=str).encode()).hexdigest()[:16]


def oat_tasks() -> list[dict]:
    """One parameter at a time, 5 seeds each, test window only; plus 20 baseline seeds."""
    tasks = [{"kind": "hmm", "window": "oos", "seed": s, "params": {}, "tag": "baseline"}
             for s in BASELINE_SEEDS]
    for name, values in GRID.items():
        for v in values:
            if v == BASE[name]:
                continue
            tasks += [{"kind": "hmm", "window": "oos", "seed": s, "params": {name: v},
                       "tag": f"oat:{name}"} for s in OAT_SEEDS]
    return tasks


def knn_tasks() -> list[dict]:
    tasks = [{"kind": "knn", "window": "oos", "seed": 0, "params": {}, "tag": "knn:baseline"}]
    for name in list(KNN_GRID) + list(KNN_SHARED):
        values = KNN_GRID.get(name) or GRID[name]
        base = BASE[name]
        tasks += [{"kind": "knn", "window": "oos", "seed": 0, "params": {name: v},
                   "tag": f"knn:{name}"} for v in values if v != base]
    return tasks


def joint_tasks() -> list[dict]:
    """Random joint draws from the grid, each with its own seed, on both windows."""
    rng = random.Random(JOINT_SEED)
    tasks = []
    for i in range(N_JOINT):
        params = {name: rng.choice(values) for name, values in GRID.items()}
        seed = rng.randint(1, 10_000)
        for window in ("oos", "tune"):
            tasks.append({"kind": "hmm", "window": window, "seed": seed, "params": params,
                          "tag": f"joint:{i}"})
    return tasks


# ----------------------------------------------------------------- amendment (paper hints)
# Added 2026-09-30 after paper_hints.md, before any sweep result was looked at.
PAPER_DATA = {"assets": "paper", "outcome": "log"}
PAPER_SCHEDULE = {"refit_frequency": 1, "order_selection_frequency": 5}


def paper_tasks() -> list[dict]:
    """E1: paper data mapping; E2: + paper's daily refit / weekly K; E3: + Ledoit-Wolf
    regime covariances; E4: 100 joint draws under the paper data mapping; KNN under it."""
    w = "paper_oos"
    tasks = [{"kind": "hmm", "window": w, "seed": s, "params": dict(PAPER_DATA), "tag": "E1"}
             for s in range(1, 11)]
    tasks += [{"kind": "hmm", "window": w, "seed": s,
               "params": {**PAPER_DATA, **PAPER_SCHEDULE}, "tag": "E2"} for s in range(1, 6)]
    tasks += [{"kind": "hmm", "window": w, "seed": s,
               "params": {**PAPER_DATA, "regime_cov": "lw"}, "tag": "E3"} for s in range(1, 6)]
    tasks += [{"kind": "knn", "window": w, "seed": 0, "params": {**PAPER_DATA, "knn_neighbors": k},
               "tag": "E-knn"} for k in (10, 25, 50, 100, 200)]
    rng = random.Random(JOINT_SEED + 1)
    for i in range(100):
        params = {name: rng.choice(values) for name, values in GRID.items()}
        params.update(PAPER_DATA, regime_cov=rng.choice(["diag", "lw"]))
        tasks.append({"kind": "hmm", "window": w, "seed": rng.randint(1, 10_000),
                      "params": params, "tag": f"E4:{i}"})
    return tasks


# ----------------------------------------------------------------- R4 (pre-registered rule)
# Settings picked by the rules once the sweeps finished; each rerun under the paper data
# mapping over 20 seeds. R4-R3: the draw with the best *tuning-window* Sharpe (joint:118).
# R4-R2: the only E4 draw matching both turnover and drawdown (E4:53). R4-x66 is exploratory:
# E4:66 is the draw nearest the paper on turnover *and* average allocation together.
def r4_tasks() -> list[dict]:
    joint = {t["tag"]: t["params"] for t in joint_tasks()}
    e4 = {t["tag"]: t["params"] for t in paper_tasks() if t["tag"].startswith("E4:")}
    picks = {"R4-R3": {**joint["joint:118"], **PAPER_DATA}, "R4-R2": e4["E4:53"],
             "R4-x66": e4["E4:66"]}
    return [{"kind": "hmm", "window": "paper_oos", "seed": s, "params": p, "tag": tag}
            for tag, p in picks.items() for s in range(1, 21)]
