# Which measurement convention did the paper use? (passive benchmarks only)

*Written by the conventions subagent; saved and extended by the main session. Full grid in
`results.json`. Run it with `PYTHONPATH=../../paper-replication/src
../../paper-replication/.venv/bin/python conventions.py` (about 4 minutes).*

The paper's targets are SPX Sharpe 1.18 with max drawdown −14.62%, and equal weight (EW) 1.59
with −9.87%. The replication gets SPX 1.355 / −18.76% and EW 1.676 / −7.96%.

## The grid: 69,120 conventions

| Dimension | Values |
|---|---|
| Price basis | adjusted / raw close |
| SPX series | SPY / ^GSPC / ^SP500TR |
| Other sleeves | ETFs (TLT, GLD, USO, UUP) / futures (TLT, GC=F, CL=F, DX-Y.NYB) |
| Returns | simple / log (portfolio return = w·log r) |
| EW rebalancing | daily / monthly / buy-and-hold |
| Window | start 1, 2, 5 or 6 June 2023 × end 13, 18, 19 or 20 February 2026 |
| Risk-free rate | none / subtracted (excess) / subtracted in the numerator only (T-bills, DTB3) |
| Annualisation, ddof | 252 / 260 / 365 days; ddof 0 / 1 |
| Frequency | daily, or monthly × √12 |
| Drawdown | compounded / additive relative / additive absolute |

Score = |ΔSharpe SPX| + |ΔSharpe EW| + 10 × (|ΔMDD SPX| + |ΔMDD EW|). A 1-point drawdown miss
counts like a 0.1 Sharpe miss.

## Result

- **No convention matches all four targets** (within 0.03 Sharpe and 0.5 points of drawdown).
- **162 conventions match both Sharpes within 0.03.** All of them use the **^GSPC price index**
  for SPX with adjusted ETFs for the other sleeves.
- **EW drawdown:** −9.87% is out of reach; the deepest EW drawdown anywhere in the grid is
  −8.89%.
- **SPX drawdown:** −14.62% is reached only with an *additive* drawdown. Compounded, it is
  about −18.8% to −19.0%.

| Convention | SPX Sharpe | SPX MDD | EW Sharpe | EW MDD | Score |
|---|---|---|---|---|---|
| A: best overall (monthly Sharpe with a T-bill rate, about 33 data points) | 1.197 | −14.60% | 1.591 | −6.84% | 0.324 |
| B: ^GSPC, log returns, buy-and-hold EW, 5 Jun 2023 to 20 Feb 2026, no rf, daily, additive drawdown | 1.192 | −15.39% | 1.576 | −6.88% | 0.402 |
| C: ^GSPC, log returns, daily-rebalanced EW, 1 Jun 2023 to 19 Feb 2026, no rf, 260 days, additive drawdown | 1.251 | −15.13% | 1.504 | −6.95% | 0.499 |
| D: the replication | 1.355 | −18.76% | 1.676 | −7.96% | 0.865 |

## How far one change moves the benchmarks (from the replication)

| Change | SPX Sharpe | EW Sharpe | Notes |
|---|---|---|---|
| Subtract T-bills | −0.30 | −0.51 | |
| Log returns | −0.07 | −0.19 | |
| ^GSPC for SPX | −0.06 | −0.02 | |
| Raw closes | −0.09 | −0.24 | |
| Annualise with 365 days | +0.28 | +0.34 | |
| Additive drawdown | | | SPX drawdown becomes −14.3% |

## The paper's own figure

The paper's cumulative log-return figure (`benchmark_cum_pnl.png`) tracks **^GSPC log returns
counted from 5 June 2023**. It passes −0.04 at the October 2023 low, 0.36 at the February 2025
peak and 0.15 at the April 2025 trough, and ends at 0.48. SPY with dividends would end near 0.51.
The figure's EW line ends at 0.35, which is the *daily-rebalanced* w·log r portfolio.

## Addendum (main session): the bond sleeve

The grid above always used TLT as the bond. The source-mining subagent (`../paper_hints.md`)
found that **IEF** reconciles the paper. With ^GSPC, IEF, GLD, USO and UUP, log returns,
daily-rebalanced EW, 5 June 2023 to 19 February 2026, no risk-free rate and 252 days:

| | Sharpe | MDD compounded | MDD additive, absolute | MDD additive, relative | Paper |
|---|---|---|---|---|---|
| SPX | **1.175** | −18.90% | −20.95% | −15.39% | 1.18 / −14.62% |
| EW | **1.588** | −7.71% | −8.02% | −6.59% | 1.59 / −9.87% |

**Conclusion.** The **Sharpe convention is identified**: ^GSPC and IEF, weighted daily log
returns, √252, no risk-free rate, 5 June 2023 to 19 February 2026. **The drawdown convention is
not identified**: no definition reproduces both published drawdowns, so the paper's drawdown
figures are treated as unreliable targets from here on. This convention is the paper data
mapping used in stage E of `../PLAN.md`.

## Strategies under these conventions (replication weights, recomputed)

| Convention | HMM Sharpe / MDD | KNN Sharpe / MDD |
|---|---|---|
| Paper | 2.18 / −5.43% | 1.81 / −12.52% |
| D, the replication | 1.59 / −9.35% | 0.79 / −13.20% |
| B | 1.47 / −8.83% | 0.58 / −14.64% |
| C | 1.41 / −8.93% | 0.61 / −14.39% |
| B with one extra day of lag | 1.32 / −10.7% | −0.07 / −24.3% |

**The conventions that fit the benchmarks lower the strategies' Sharpe ratios.** The gap to
2.18 is not a measurement artefact. Turnover does not depend on the convention: HMM 0.0166
(paper 0.0079), KNN 0.495 (paper 0.567).
