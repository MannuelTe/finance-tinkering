# Wasserstein HMM replication

*Last updated: 2026-09-20*

Replication and stress-test of Boukardagha, [*Explainable Regime Aware Investing*](https://arxiv.org/abs/2603.04441)
(arXiv:2603.04441): a causal Wasserstein hidden Markov model (HMM) with regime templates and a
turnover-penalized optimizer, versus a k-NN comparator and passive benchmarks.

## Results in brief

**1. The paper's headline is not reproduced** ([`paper-replication/`](paper-replication)).
Out-of-sample 2023-06-02 to 2026-02-20 (682 sessions), gross of costs:

| Strategy | Published Sharpe | Reproduced Sharpe | Reproduced max drawdown |
|---|---:|---:|---:|
| Wasserstein HMM | 2.18 | **1.59** | -9.35% |
| KNN | 1.81 | **0.79** | -13.20% |
| Equal weight | 1.59 | **1.68** | -7.96% |
| SPY | 1.18 | **1.36** | -18.76% |

- The HMM does not beat equal weight, and the paper's exact numbers cannot be recovered from its published specification.
- What does hold: the HMM is far more stable than KNN (one-way turnover 1.7% vs 49.5% per day). After 5 bp costs, HMM Sharpe is 1.57 while KNN drops to 0.38.
- Supported claim: persistent regimes stabilize portfolio construction relative to an unsmoothed KNN. Not supported: superiority over passive diversification.
- Extension: a diversified bond sleeve instead of TLT alone lifts HMM Sharpe from 1.59 to about 1.78, but equal weight improves too (1.68 to 1.80), so the HMM still does not clearly win.

**2. Blocked validation of K helps modestly** ([`overfitting-test/`](overfitting-test)).
Choosing the number of states on several purged random blocks instead of the last 126 days,
backtested 2019 to 2026 (1,794 days), 30 seeds:

| | last-126-day selector | blocked CV |
|---|---:|---:|
| Mean Sharpe | 0.863 | **0.972** |
| One-way turnover / day | 1.26% | 0.87% |
| Mean selected K | 2.69 | 2.32 |

- Paired Sharpe gain **+0.11** (95% CI +0.04 to +0.17); blocked CV wins in 24 of 30 seeds (paired t-test p = 0.002; block bootstrap p about 0.005-0.007).
- A modest effect (about 13% relative), driven mostly by 2023 to 2026; 2019 to 2022 is roughly a tie (2022 is negative for both).
- Blocked CV picks fewer states and switches less often, consistent with the original selector overfitting one window, though the study does not prove that cause.
- Max drawdown is about the same (-25.5% vs -26.6% on average). It is robust to algorithm randomness, not a test on independent market data, and is not a claim that either beats a passive portfolio.

The overfitting-test folder also ships a read-only MCP server ([`MCP.md`](overfitting-test/MCP.md)) exposing the HMM maths.

> Research software, not investment advice. One market history, gross-of-cost backtests.
