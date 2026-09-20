# Finance Tinkering

*Last updated: 2026-09-20*

Pet projects around fintech, trading and quantitative research. Each folder is self-contained
(own README, dependencies and tests where applicable).

| Folder | What it is |
|---|---|
| [`harness/`](harness) | Support tools and artefacts. |
| [`wasserstein-hmm-replication/`](wasserstein-hmm-replication) | Support tools and artefacts. |
| [`beta-scanner/`](beta-scanner) | Support tools and artefacts. |
| [`notes/`](notes) | Support tools and artefacts. |
| [`archive/`](archive) | Support tools and artefacts. |
| [`legacy/`](legacy) | Older projects: [`tradebot-overnight/`](legacy/tradebot-overnight), [`ib-merger-model/`](legacy/ib-merger-model). |

Nested project READMEs:

- `harness/`: [`theses/volatility_frontier`](harness/theses/volatility_frontier), [`theses/metals_hedged_frontier`](harness/theses/metals_hedged_frontier), [`research/wasserstein_hmm_replication`](harness/research/wasserstein_hmm_replication).
- `wasserstein-hmm-replication/`: [`paper-replication/`](wasserstein-hmm-replication/paper-replication), [`overfitting-test/`](wasserstein-hmm-replication/overfitting-test).
- `legacy/tradebot-overnight/`: [`paper/`](legacy/tradebot-overnight/paper), [`graphics_paper/`](legacy/tradebot-overnight/graphics_paper).
- `legacy/ib-merger-model/`: [`app/`](legacy/ib-merger-model/app).

`harness` and `legacy/tradebot-overnight` share an ancestry; `harness` also carries its own
copy of the Wasserstein replication under `research/`.

> Research software, not investment advice. Secrets live in local `.env` files, which are git-ignored;
> only `.env.example` templates are tracked. GitHub Actions only run from the repo-root `.github/`,
> so the per-project workflow files inside subfolders are inactive until moved there.
