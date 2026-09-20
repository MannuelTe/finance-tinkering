# Finance Tinkering

*Last updated: 2026-09-20*

Pet projects around fintech, trading and quantitative research. Each folder is self-contained
(own README, dependencies and tests where applicable).

| Folder | What it is |
|---|---|
| [`tradebot-overnight/`](tradebot-overnight) | Multi-currency ETF portfolio bot (IBKR paper / in-memory sim) with a volatility-aware SPY close-to-open "overnight" sleeve, Streamlit dashboard, Postgres/Alembic state, and a LaTeX paper on the underlying maths. |
| [`thesis-harness/`](thesis-harness) | Successor to the tradebot: turns a plain-text investment thesis into a LaTeX/PDF research paper with backtest, bootstrap uncertainty and figures (`thesispaper`), plus a generic `tradebot` toolkit. Includes example theses (volatility frontier, metals-hedged frontier). |
| [`wasserstein-hmm-replication/`](wasserstein-hmm-replication) | Replication of *Explainable Regime Aware Investing* (Wasserstein HMM / k-NN regimes), plus an overfitting test using blocked validation, with a read-only MCP server (Muse Code compatible) for the HMM maths. |
| [`ib-merger-model/`](ib-merger-model) | Investment-banking M&A pet project: three fictional banks, merger model (xlsx), Streamlit app, decision memo and glossary. |
| [`beta-scanner/`](beta-scanner) | Beta of a stock vs SPY / RSP (equal-weight) and an S&P 500 mid-cap scanner for names where the two betas diverge; early notebooks. |
| [`notes/`](notes) | Research notes (e.g. how to gauge the impact of the regime-investing paper). |
| [`archive/`](archive) | Old standalone SPY overnight research script (read-only IBKR, no order submission). |

Nested project READMEs:

- `tradebot-overnight/`: [`paper/`](tradebot-overnight/paper) (LaTeX maths paper), [`graphics_paper/`](tradebot-overnight/graphics_paper) (figure pipeline).
- `thesis-harness/`: [`theses/volatility_frontier`](thesis-harness/theses/volatility_frontier), [`theses/metals_hedged_frontier`](thesis-harness/theses/metals_hedged_frontier), [`research/wasserstein_hmm_replication`](thesis-harness/research/wasserstein_hmm_replication).
- `wasserstein-hmm-replication/`: [`paper-replication/`](wasserstein-hmm-replication/paper-replication), [`overfitting-test/`](wasserstein-hmm-replication/overfitting-test).
- `ib-merger-model/`: [`app/`](ib-merger-model/app) (Streamlit workbench).

`tradebot-overnight` and `thesis-harness` share an ancestry; `thesis-harness` also carries its own
copy of the Wasserstein replication under `research/`.

> Research software, not investment advice. Secrets live in local `.env` files, which are git-ignored;
> only `.env.example` templates are tracked. GitHub Actions only run from the repo-root `.github/`,
> so the per-project workflow files inside subfolders are inactive until moved there.
