# Checking the impact of *Explainable Regime Aware Investing*

Paper: Amine Boukardagha, arXiv:2603.04441 (March 2026). https://arxiv.org/abs/2603.04441

The paper is about six months old, so very few citations are expected. I found no impact data for it. The paper is a single-author preprint, is not peer reviewed as far as I can tell, and I found no journal version. The replication in `wasserstein-hmm-replication` also showed that its headline numbers do not reproduce.

## Where to check impact

| Source | What it gives you |
|---|---|
| [Google Scholar](https://scholar.google.com) | Broadest citation counts ("Cited by"), but includes low-quality citations |
| [Semantic Scholar](https://www.semanticscholar.org) | Citation counts plus "highly influential" citations; handles arXiv well |
| [OpenAlex](https://openalex.org) | Free, open citation database with an API, useful for scripting |
| arXiv abstract page | Links to related-work and citation-context tools (Connected Papers, scite, Papers with Code) |
| SSRN / [RePEc-IDEAS](https://ideas.repec.org/s/arx/papers16.html) | Download counts for finance papers; the paper is already indexed on IDEAS |
| Altmetric / social attention | Mentions on X, Reddit r/quant, blogs; more informative than citations for a paper this new |

## Comparable papers, last five years

I could not get citation counts for any of these, and most come from memory rather than a ranked source. Check each one on Google Scholar before relying on it.

- **Horvath, Issa & Muguruza, "Clustering Market Regimes using the Wasserstein Distance."** The closest methodological relative, since it also uses Wasserstein distance for regimes.
- **Nystrup, Kolm & Lindström, statistical jump models for regime-based allocation** (2021, "Feature selection in jump models"). Argues jump models detect regimes more stably than HMMs, which is the same label-instability and turnover problem the Wasserstein paper targets.
- **Shu, Yu & Mulvey, "Dynamic Asset Allocation with Asset-Specific Regime Forecasts"** (2024). https://arxiv.org/pdf/2406.09578
- **Wang, Lin & Mikhelson, "Regime-Switching Factor Investing with Hidden Markov Models"** (2020). https://www.mdpi.com/1911-8074/13/12/311
- **"Regime-Based Portfolio Allocation Using Hidden Markov Models and Reinforcement Learning"** (May 2026). https://arxiv.org/abs/2605.27848 (same SPY / TLT / GLD setup as this replication)
- **Gu, Kelly & Xiu, "Empirical Asset Pricing via Machine Learning"** (2020). Not regime-specific, but one of the most cited machine learning finance papers of the period, so a useful benchmark for what high impact looks like.

Citation counts scale strongly with age, so compare papers by publication date. A 2026 preprint should not be compared directly with a 2020 paper.

## Sources

- https://arxiv.org/pdf/2603.04441
- https://arxiv.org/list/q-fin.PM/2026-03
- https://ideas.repec.org/s/arx/papers16.html
- https://arxiv.org/pdf/2406.09578
- https://www.mdpi.com/1911-8074/13/12/311
- https://arxiv.org/abs/2605.27848
