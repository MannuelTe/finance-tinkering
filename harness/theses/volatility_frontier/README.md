# Volatility frontier thesis

Reproducible research package for a volatility-gated SPY/TLT frontier strategy. It contains the
human thesis, causal strategy source, comparison runner, generated LaTeX/PDF, figures, and a
broker-safe plan-only IBKR adapter in `research/volatility_frontier_ibkr_plan.py`.

## Build

From the repository root:

```bash
PYTHONPATH=src python -m thesispaper check volatility_frontier
PYTHONPATH=src python -m thesispaper run volatility_frontier
PYTHONPATH=src python theses/volatility_frontier/analysis.py
PYTHONPATH=src python -m thesispaper build volatility_frontier
```

The price download is cached under `data/`. The cache and derived JSON/figures are ignored by the
parent repository, while `paper.tex` and `paper.pdf` are trackable.

## Files intended for GitHub

- `thesis.md` and `thesis.yaml`: prose claim and machine-readable experiment.
- `strategy.py`: no-lookahead model logic.
- `analysis.py`: sine/linear/quadratic comparison and plots.
- `sections/thesis_math.tex`: mathematical specification and discussion.
- `paper.tex` and `paper.pdf`: generated paper.
- `model_trade_ledger.csv`: generated model target changes (not broker fills).

Nothing here is investment advice. The IBKR planner refuses live mode and cannot transmit orders.
