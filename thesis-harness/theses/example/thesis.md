# Momentum tilt between SPY and TLT

**Thesis.** Equities (SPY) and long-dated Treasuries (TLT) take turns leading. If trailing
six-month return of one is higher than the other, that ranking persists on a one-month horizon
often enough to tilt a static 60/40 portfolio toward the leader.

**Rule.** Each month-end, compute the trailing 126-session return of SPY and TLT. Start from a
60/40 SPY/TLT portfolio and shift `tilt` (default 20 percentage points) of weight from the
laggard to the leader. Rebalance monthly; costs of 5 bp per unit of turnover.

**Benchmark.** SPY buy-and-hold (reported); static 60/40 is the theoretical reference in the math.

**Hypotheses.**
- H1: the tilted portfolio has a higher Sharpe ratio than static 60/40.
- H2: the improvement survives 5 bp costs.

**Caveat.** A deliberately simple public example for demonstrating the pipeline. The default
data is synthetic so it runs offline; it says nothing about real markets.
