# Finance Tinkering

*Last updated: 2026-09-29*

Pet projects around fintech, trading and quantitative research. Each folder is self-contained
(own README, dependencies and tests where applicable).

| Folder | What it is |
|---|---|
| [`harness/`](harness) | Support tools and artefacts. |
| [`wasserstein-hmm-replication/`](wasserstein-hmm-replication) | Replication of *Explainable Regime Aware Investing* (Wasserstein HMM / k-NN regimes), plus an overfitting test whose blocked-validation fix gave a modest but statistically robust improvement. |
| [`market-surveillance/`](market-surveillance) | Pre-announcement insider-dealing screen (event study) and a MiFIR RTS 22 transaction-report validator with ARM reconciliation; Bloomberg pull spec included. |
| [`TaxHarvest/`](TaxHarvest) | Plans conditional tax-lot sales around a dollar tax-saving goal. It selects enough eligible loss capacity for a chosen confidence, caps actual sales at the goal, and screens US wash sales and Canadian superficial losses. A weekly review re-checks the odds with fresh prices and says when to lock losses in. Includes a Swiss control case, worked examples, stress tests, and animations. |
| [`uranium-signatures/`](uranium-signatures) | How fast uranium news gets into prices, and whether anyone trades before it. On 48 source-checked events, bullish news is half-priced in ~2 days and bearish in ~2–3 weeks. A pre-announcement screen finds no insider footprints above its detection limits; its one flag traces to public news. Adds lead-lag against physical and spot prices, a walk-forward backtest, and a primer on price discovery. |
| [`beta-scanner/`](beta-scanner) | Beta of a stock vs SPY / RSP (equal-weight) and an S&P 500 mid-cap scanner for names where the two betas diverge; early notebooks. |
| [`notes/`](notes) | Research notes (e.g. how to gauge the impact of the regime-investing paper). |
| [`archive/`](archive) | Old standalone SPY overnight research script (read-only IBKR, no order submission). |
| [`legacy/tradebot-overnight/`](legacy/tradebot-overnight) | Multi-currency ETF portfolio bot (IBKR paper / in-memory sim) with a volatility-aware SPY close-to-open "overnight" sleeve, Streamlit dashboard, Postgres/Alembic state, and a LaTeX paper on the underlying maths. |
| [`legacy/ib-merger-model/`](legacy/ib-merger-model) | Investment-banking M&A pet project: three fictional banks, merger model (xlsx), Streamlit app, decision memo and glossary. |

`harness` and `legacy/tradebot-overnight` share an ancestry; `harness` also carries its own
copy of the Wasserstein replication under `research/`.

> Research software, not investment advice. Secrets live in local `.env` files, which are git-ignored;
> only `.env.example` templates are tracked. GitHub Actions only run from the repo-root `.github/`,
> so the per-project workflow files inside subfolders are inactive until moved there.
