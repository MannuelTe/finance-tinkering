# Wasserstein HMM replication

*Last updated: 2026-09-20*

Replication and stress-testing of Boukardagha, [*Explainable Regime Aware Investing*](https://arxiv.org/abs/2603.04441)
(arXiv:2603.04441): a causal Wasserstein hidden Markov model with persistent regime templates,
conditional return estimation and a transaction-penalized portfolio optimizer, compared against a
k-NN regime comparator and passive benchmarks.

| Folder | What it is |
|---|---|
| [`paper-replication/`](paper-replication) | Independent implementation and reproducibility audit of the paper: HMM, KNN comparator, optimizer, benchmarks, figures and a write-up. |
| [`overfitting-test/`](overfitting-test) | Tests whether the HMM's choice of the number of states K is overfit to one validation window, using purged, blocked validation (backtest from 2019 instead of 2023). Also ships a read-only MCP server ([`MCP.md`](overfitting-test/MCP.md)) exposing the HMM maths, Muse Code compatible. |

Each folder is self-contained (own `pyproject.toml`, tests and results). Start with
`paper-replication`, then read `overfitting-test`, which changes only the K-validation scheme.

> Research software, not investment advice.
