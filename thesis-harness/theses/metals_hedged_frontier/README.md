# Metals-hedged frontier thesis

Reproducible research package for a SPY/TLT core hedged with a GLD/SLV sleeve. The static reference
is 48% SPY, 32% TLT, 14% GLD, and 6% SLV. The active model moves the metals share between 5% and
35% using a rolling efficient frontier and a causal five-session volatility signal.

## Build

```bash
PYTHONPATH=src python -m thesispaper check metals_hedged_frontier
PYTHONPATH=src python -m thesispaper run metals_hedged_frontier
PYTHONPATH=src python theses/metals_hedged_frontier/analysis.py
PYTHONPATH=src python -m thesispaper build metals_hedged_frontier
```

The resulting `paper.tex` and `paper.pdf` are trackable. Cached prices and generated figures can be
recreated with the commands above. The IBKR planner is
`research/metals_hedged_frontier_ibkr_plan.py`; it refuses live mode and cannot transmit orders.
