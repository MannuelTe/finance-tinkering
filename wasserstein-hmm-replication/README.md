# Wasserstein HMM replication

*Last updated: 2026-09-30*

Replication and stress-test of Boukardagha, [*Explainable Regime Aware Investing*](https://arxiv.org/abs/2603.04441)
(arXiv:2603.04441): a causal Wasserstein hidden Markov model (HMM) with regime templates and a
turnover-penalized optimizer, versus a k-NN comparator and passive benchmarks.

## Where the replication stands

**Verdict: the paper's data and measurement are reproduced; its headline results are not.** The
HMM's 2.18 Sharpe can be reached, but only by settings that contradict the paper's own reported
behaviour. The KNN's 1.81 cannot be reached at all.

| Paper claim | Status | Evidence |
|---|---|---|
| Data and benchmarks (SPX 1.18, equal weight 1.59) | **Reproduced** | ^GSPC, IEF, weighted log returns, 5 Jun 2023 to 19 Feb 2026 give 1.175 and 1.588 (stage 3). Drawdowns do not reconcile under any definition. |
| HMM turnover 0.0079 and drawdown −5.43% | **Reproduced, with tuning** | One setting gives 0.0080 and −6.5% over 20 seeds (stage 3). |
| HMM Sharpe 2.18 | **Not reproduced** | That same setting gives 1.70 ± 0.32. Plausible settings span 1.23 to 2.40, and the ones above 2.2 barely trade (< 0.001 a day). |
| HMM beats equal weight | **Not supported** | Matched settings exceed equal weight (1.59) by about 0.1, less than one seed standard deviation. |
| KNN Sharpe 1.81, turnover 0.567 | **Not reproduced** | 0.3 to 1.3 under every setting with KNN-like turnover that keeps the paper's stated feature windows. The best is 1.61, which needs a 60-day momentum window, but the paper states 20. |
| Regime persistence stabilises allocations versus KNN | **Supported** | HMM turnover stays below 0.08 a day in all 811 HMM runs; KNN runs at 0.37 to 0.63 unless heavily penalised (stages 1 and 3). |

The most economical explanation for 2.18 is the paper's *average allocation*, not its timing.
Holding the reported average weights fixed (much gold, no oil) gives 2.34 on the same data. Across
settings, the more the HMM trades, the further it falls behind a static hold of its own average mix.
Gold was the best asset over 2023 to 2026 (Sharpe 1.81), so any setting that locks in gold early
looks good. The paper's result is consistent with one favourable reading of an underspecified
method on a single, gold-friendly window.

**What would settle it:** the author's code or the exact turnover penalty, seed and K-selection
settings, and the paper's daily weights. Without them, the replication's best estimate for the paper's specification
is a Sharpe of about 1.7, with 90% of seeds between 1.3 and 2.1.

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

**2. The change worked: blocked validation of K improves results modestly** ([`overfitting-test/`](overfitting-test)).
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

**3. Tuning what the paper leaves unstated reaches 2.18 only with near-static portfolios** ([`parameter-tuning/`](parameter-tuning/FINDINGS.md)).
838 backtests over 16 unstated parameters, the paper's data mapping (^GSPC, IEF, log returns) and seeds:

- Plausible settings put the middle 90% of HMM Sharpes between **1.23 and 2.40**; 19% reach the published 2.18.
- Rerun over 20 seeds, the setting that matches the paper's turnover (0.0080 vs 0.0079) and drawdown has Sharpe **1.70 ± 0.32**; 1 seed in 20 reaches 2.18.
- Every Sharpe above about 2.2 barely trades (turnover below 0.001). Holding the paper's own average allocation fixed gives 2.34. Across draws, the model's timing lowers Sharpe relative to holding its average mix.
- Choosing settings on 2019 to 2023 data barely predicts 2023 to 2026 results (rank correlation 0.15). The KNN comparator (1.81) is not reproduced under any setting tried.

> Research software, not investment advice. One market history, gross-of-cost backtests.
