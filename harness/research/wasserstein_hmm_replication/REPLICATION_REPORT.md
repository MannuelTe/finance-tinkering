# Clean-room replication: Explainable Regime Aware Investing

## Verdict

The paper's architecture was reproduced, but its numerical claims are not independently reproducible from the publication. The arXiv bundle contains no implementation or data snapshot, labels its reported model "Commercial V2.0," and omits the exact tickers, test split, HMM settings, feature scaling, template initialization, optimizer coefficients, and realized-cost convention.

| Method | Sharpe pub/rep | Max DD pub/rep | Turnover pub/rep |
|---|---:|---:|---:|
| Wasserstein HMM | 2.18 / 1.59 | -5.43% / -9.35% | 0.0079 / 0.0166 |
| KNN | 1.81 / 0.79 | -12.52% / -13.20% | 0.5665 / 0.4949 |
| Equal weight | 1.59 / 1.68 | -9.87% / -7.96% | - |
| SPX | 1.18 / 1.36 | -14.62% / -18.76% | - |

## What was reproduced

- Strictly lagged return, 60-session volatility, and 20-session momentum features.
- Expanding-window Gaussian HMM with predictive model-order selection.
- Six persistent templates matched with closed-form Gaussian 2-Wasserstein distance.
- Template-probability-weighted conditional return moments.
- Long-only, capped, transaction-penalized mean-variance allocation.
- An expanding KNN conditional-moment baseline using the same optimizer.

## Explicit assumptions

- Yahoo adjusted-close ETFs: SPY, TLT, GLD, USO, and UUP.
- OOS: 2023-06-02 through 2026-02-20 (682 observations).
- HMM candidates [2, 3, 4, 5, 6]; six templates; refit every 10 sessions; order selection every 63 sessions.
- Risk aversion 3.0, turnover penalty 0.0001, maximum weight 60%; reported primary results are gross, with a separate 5-bp realized-cost result in `results.json`.

## Why an exact match fails

1. The empirical specification is underdetermined: changing any omitted ticker, scaling, covariance type, refit cadence, or penalty changes the result materially.
2. The paper's own source contains an older result table and a newer "Commercial V2.0" table while reusing figure files.
3. Its timing notation is inconsistent: features include `r_t`, all features are said to stop at `t-1`, and the pseudocode realizes `w_t' r_t`.
4. Its HMM Gaussian means/covariances are 15-dimensional feature moments, yet the displayed portfolio equation uses them as five-asset return moments without specifying the projection.
5. Published SPX benchmark statistics do not match the disclosed Yahoo adjusted-close window under standard Sharpe/drawdown definitions.

This is a research reproduction, not investment advice or evidence of future returns.
