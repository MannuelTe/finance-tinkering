# Pre-registration: tuning the paper's unstated parameters

*Written 2026-09-30, before any sweep result was seen. The grid is in `src/ptune/grid.py`.*

## Question

The paper (Boukardagha 2026, arXiv:2603.04441) reports, for 2023-06-02 to 2026-02-20:

| | Sharpe | Max drawdown | Daily turnover |
|---|---:|---:|---:|
| Wasserstein HMM | 2.18 | −5.43% | 0.0079 |
| KNN | 1.81 | −12.52% | 0.5665 |
| Equal weight | 1.59 | −9.87% | |
| SPX | 1.18 | −14.62% | |

The replication gets HMM 1.59 / −9.35% / 0.0166, using guesses for many choices the paper
does not state. How much of the gap can those unstated choices explain, and what range of
results do plausible choices produce?

## Design

1. **Measurement convention** (subagent, `conventions/`): find the risk-free rate, data and
   window conventions that reproduce the *passive* benchmarks. Those have no model
   parameters, so this cannot overfit the model. Apply the best convention to every strategy.
2. **One at a time (OAT):** vary each unstated parameter over its grid, holding the others at
   the replication's values. 5 seeds per setting, and 20 seeds for the baseline itself, to
   measure how much the seed alone moves the result.
3. **Joint sample:** 200 random draws from the full grid, each with its own random seed. Each
   draw runs on the test window *and* on an earlier tuning window (2019-01-02 to 2023-05-31).
4. **KNN:** vary the number of neighbours and the shared optimizer and feature parameters.

## Decision rules, fixed in advance

- **R1, specification interval.** Over the 200 joint draws, report the 5th to 95th percentile of
  test-window Sharpe, drawdown and turnover, and the share of draws with Sharpe ≥ 2.18. This is
  the interval of results that plausible readings of the paper produce.
- **R2, calibration on non-return targets.** A draw "matches" the paper's non-return numbers if
  its test-window HMM turnover is within ±25% of 0.0079 (0.0059 to 0.0099) and its max
  drawdown is within ±20% of −5.43% (−6.5% to −4.3%). Report the Sharpe distribution of
  the matching draws. This asks: if we reconstruct the paper's trading behaviour, do we also
  get its Sharpe?
- **R3, honest selection.** Among the 200 draws, choose the one with the best Sharpe on the
  *tuning* window, and report its test-window Sharpe once. Also report the rank correlation
  between tuning-window and test-window Sharpe across draws, to see whether choosing settings
  on past data carries over.
- **R4, rerun the engine.** Rerun the paper's engine with the best-supported convention and the
  settings from R2/R3, over 20 seeds, and compare with the published numbers.
- **Multiple testing.** When a best-of-N result is quoted, also give the Deflated Sharpe Ratio
  (Bailey & López de Prado, 2014), which accounts for the number of trials.

Nothing in the grid or these rules is changed after results come in. Anything added later is
labelled as exploratory.

## Amendment 1 (2026-09-30, after `paper_hints.md`, before looking at any sweep result)

The source-mining subagent found that the paper's own files pin down the data mapping (see
`paper_hints.md`, sections 1 and 6):

- SPX is the S&P 500 **price index** `^GSPC` (not SPY), and BOND is most likely **IEF** (not TLT).
- The test window is **2023-06-05 to 2026-02-19** (680 sessions).
- Portfolio returns and Sharpe use **weighted daily log returns**, √252, with no risk-free rate.

With that mapping the passive benchmarks reproduce: SPX Sharpe 1.175 (published 1.18), equal
weight 1.588 (published 1.59). Because these hints come from the paper and not from sweep
results, they are added as a pre-registered stage E. They do not replace stages 1–4.

- **E1:** replication settings, paper data mapping and log outcomes, 10 seeds.
- **E2:** as E1, plus the paper's pseudocode schedule (refit daily, re-choose K weekly), 5 seeds.
- **E3:** as E1, plus Ledoit–Wolf regime covariances (hinted for KNN), 5 seeds.
- **E4:** 100 joint draws from the same grid under the paper data mapping, with the covariance
  estimator also drawn. This gives the specification interval (R1) and calibration (R2) under the
  paper's data.
- **E-knn:** KNN under the paper data mapping, with 10 to 200 neighbours.
- **R2b, new calibration target:** the paper's average HMM allocation (SPX 0.26, BOND 0.22,
  GOLD 0.22, OIL 0.00, USD 0.29). Report the draws closest to it in L1 distance, and their Sharpe.
