# A gold/silver hedge for a dynamic SPY/TLT frontier

## Portfolio construction

The investable universe is SPY, TLT, GLD, and SLV. To prevent a four-asset rolling optimizer from
turning estimation noise into extreme allocations, the assets are grouped into two fixed internal
sleeves:

- Core: 60% SPY and 40% TLT.
- Precious metals: 70% GLD and 30% SLV.

The neutral reference assigns 80% to the core and 20% to metals, giving total weights of 48% SPY,
32% TLT, 14% GLD, and 6% SLV. The metals allocation is constrained to 5%-35%.

At each close, the model estimates a rolling efficient frontier between the core and metals sleeve.
The mean-variance growth optimum is the neutral point. Five-session reference volatility relative
to its 21-session estimate determines whether to move toward lower or higher frontier risk. The
absolute five-session growth gap between the optimum and the static hedged reference throttles the
move. A zero growth gap means no displacement from the optimum.

The primary strategy uses a five-session sinusoidal causal kernel. Linear and quadratic kernels
are run on the identical raw signal. We separately compare the static metals-hedged reference with
unhedged static 60/40 SPY/TLT to distinguish the effect of adding metals from the timing rule.

## Data and execution

The backtest starts in January 2023, uses adjusted closes, applies targets one session after they
are formed, and charges 5 basis points per unit of turnover. GLD and SLV are treated as bullion-price
proxies, not as literal holdings of bars by the strategy. A separate IBKR paper-account planner
converts the latest four-ETF target into whole-share, non-transmitting order instructions.
