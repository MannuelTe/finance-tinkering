"""PURPOSE: expose the HMM / blocked-validation maths as a Model Context Protocol (MCP) server.
INPUTS: MCP tool calls over stdio (default) or streamable HTTP.
OUTPUTS: structured JSON results. All tools are read-only and send no data anywhere.

Run:  python -m overfit_hmm.mcp_server [--transport stdio|streamable-http] [--host H] [--port P]
"""

import argparse
import json
import math
from dataclasses import replace
from typing import Annotated, Any, Literal

import numpy as np
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from .config import ROOT, OverfitConfig
from .router import route_question
from .splits import blocked_splits

MAX_ROWS, MAX_DIMS, MAX_STATES = 6000, 30, 8

INSTRUCTIONS = (
    "Mathematics for regime models (hidden Markov models) and honest validation of them: purged "
    "random-block train/test layouts, Bayes filtering, choosing the number of states, and the "
    "results of a 30-seed overfitting study. Intended for small-business and finance questions "
    "in Zurich, Zug, Winterthur and the Lower Mainland of British Columbia, but the maths is "
    "region-agnostic. Purely mathematical topics only: call route_small_business_question first "
    "for a free-text question; governance, legal, tax and compliance questions are declined. "
    "Not investment, legal or tax advice."
)

server = MCPServer(
    name="overfit-hmm",
    title="HMM regime maths and blocked validation",
    description="Read-only maths tools for hidden Markov regime models and overfitting tests.",
    instructions=INSTRUCTIONS,
    version="0.1.0",
    website_url="https://github.com/MannuelTe/finance-tinkering",
)
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True,
                            open_world_hint=False)


def _matrix(name: str, value: list[list[float]], max_rows: int = MAX_ROWS) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty 2-D list of numbers")
    if array.shape[0] > max_rows or array.shape[1] > MAX_DIMS:
        raise ValueError(f"{name} is limited to {max_rows} rows and {MAX_DIMS} columns")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains NaN or infinite values")
    return array


@server.tool(annotations=READ_ONLY)
def route_small_business_question(
    question: Annotated[str, Field(min_length=1, max_length=2000)],
) -> dict[str, Any]:
    """Decide whether a small-business question is purely mathematical (and which tools of this
    server help) or must be declined because it is about governance, legal, tax or compliance."""
    return route_question(question)


@server.tool(annotations=READ_ONLY)
def blocked_split_layout(
    n: Annotated[int, Field(ge=200, le=100_000, description="History length in days")],
    holdout_days: Annotated[int, Field(ge=1, le=500)] = 80,
    block_len: Annotated[int, Field(ge=1, le=500)] = 80,
    random_blocks: Annotated[int, Field(ge=0, le=10)] = 3,
    gap_days: Annotated[int, Field(ge=0, le=250, description="Purge on each side of a block")] = 60,
    min_segment: Annotated[int, Field(ge=1, le=2000)] = 120,
    seed: int = 7,
) -> dict[str, Any]:
    """Build a purged random-block layout: |train|gap|TEST|gap|train| ... |gap|TEST(last days).
    Returns half-open [start, stop) index intervals and the smallest purged gap actually found
    between a train segment and a test block."""
    rng = np.random.default_rng([seed, n])
    train, tests = blocked_splits(n, holdout_days, block_len, random_blocks, gap_days,
                                  min_segment, rng)
    gaps = [t0 - b if b <= t0 else a - t1 for t0, t1 in tests for a, b in train
            if b <= t0 or a >= t1]
    return {"train_segments": [list(s) for s in train], "test_blocks": [list(t) for t in tests],
            "train_days": sum(b - a for a, b in train), "test_days": sum(b - a for a, b in tests),
            "min_purged_gap_days": min(gaps), "requested_gap_days": gap_days}


@server.tool(annotations=READ_ONLY)
def bayes_filter_step(
    prior: Annotated[list[float], Field(min_length=2, max_length=MAX_STATES)],
    transition: list[list[float]],
    likelihood: Annotated[list[float], Field(min_length=2, max_length=MAX_STATES)],
) -> dict[str, Any]:
    """One HMM Bayes update. predicted = prior @ transition (Markov step); posterior is
    predicted * likelihood, renormalised. Also returns the predictive density (the normaliser)."""
    k = len(prior)
    a = _matrix("transition", transition, MAX_STATES)
    p, lik = np.asarray(prior, float), np.asarray(likelihood, float)
    if a.shape != (k, k) or len(lik) != k:
        raise ValueError("prior, transition (k x k) and likelihood must share the same k")
    if (a < 0).any() or (p < 0).any() or (lik < 0).any():
        raise ValueError("probabilities and likelihoods must be non-negative")
    if not (np.allclose(a.sum(axis=1), 1.0) and np.isclose(p.sum(), 1.0)):
        raise ValueError("prior and each transition row must sum to 1")
    predicted = p @ a
    joint = predicted * lik
    density = float(joint.sum())
    if density <= 0:
        raise ValueError("all states have zero likelihood; posterior is undefined")
    return {"predicted": predicted.tolist(), "posterior": (joint / density).tolist(),
            "predictive_density": density}


@server.tool(annotations=READ_ONLY)
def select_hmm_order(
    features: list[list[float]],
    method: Literal["blocked", "last_window"] = "blocked",
    candidate_states: Annotated[list[int] | None, Field(max_length=MAX_STATES - 1)] = None,
    seed: int = 7,
    validation_days: Annotated[int, Field(ge=20, le=1000)] = 126,
) -> dict[str, Any]:
    """Choose the number of HMM states K for standardized features (rows = days, columns =
    variables) by penalized held-out log-likelihood. method 'blocked' uses purged random blocks
    plus the last 80 days; 'last_window' uses only the last validation_days (the original rule).
    candidate_states defaults to [2, 3, 4]. Needs the optional hmmlearn dependency and at
    least ~600 rows for 'blocked'."""
    from hmmlearn import hmm as _  # noqa: F401  pylint: disable=import-outside-toplevel
    from .selection import select_order_blocked  # pylint: disable=import-outside-toplevel
    from wasserstein_hmm.models import select_order  # pylint: disable=import-outside-toplevel

    x = _matrix("features", features)
    candidate_states = candidate_states or [2, 3, 4]
    if len(candidate_states) < 2 or any(not 2 <= k <= MAX_STATES for k in candidate_states):
        raise ValueError(f"candidate_states needs at least two values within 2..{MAX_STATES}")
    config = replace(OverfitConfig(), candidate_states=tuple(candidate_states), random_seed=seed,
                     hmm_iterations=30, validation_days=validation_days)
    chosen, scores = (select_order_blocked if method == "blocked" else select_order)(x, config)
    return {"selected_k": chosen, "scores": {str(k): (v if math.isfinite(v) else None)
                                              for k, v in scores.items()},
            "method": method, "rows": int(x.shape[0]), "columns": int(x.shape[1])}


def _study_results() -> dict[str, Any]:
    path = ROOT / "results" / "multiseed_stats.json"
    return json.loads(path.read_text())


@server.tool(annotations=READ_ONLY)
def overfitting_study_results() -> dict[str, Any]:
    """Stored results of the 30-seed study: blocked validation vs the last-126-day rule
    (Sharpe difference, paired tests, block bootstrap, by-year and by-period splits)."""
    return _study_results()


@server.resource("hmm://overfitting/multiseed-results", mime_type="application/json")
def multiseed_results_resource() -> str:
    """The same study results as a resource."""
    return json.dumps(_study_results())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
