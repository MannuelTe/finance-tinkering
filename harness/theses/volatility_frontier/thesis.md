# Volatility-gated motion on the SPY/TLT efficient frontier

## Investment thesis

Estimate a long-only, fully invested SPY/TLT mean-variance frontier using only information
available at each close. The strategy's neutral point is the portfolio that maximizes the rolling
mean-variance growth score. A static 60% SPY / 40% TLT portfolio supplies a *reference return*.
It is deliberately not called a risk-free asset: both ETFs are risky and the reference can lose
money.

At each daily decision:

1. Estimate annualized mean returns and covariance from at most 126 prior sessions.
2. Form the two-asset efficient frontier between the long-only global minimum-variance portfolio
   and the higher-estimated-return endpoint, with SPY constrained to 5%-95%.
3. Choose the frontier portfolio maximizing expected return minus 1.5 times variance as the
   growth-optimal anchor.
4. Measure five-session volatility surprise relative to a 21-session estimate for the static
   60/40 reference.
5. Gate the magnitude by the absolute five-session compound-return gap between the optimal anchor
   and 60/40. If that growth gap is zero, the target remains at the anchor.
6. Positive volatility surprise moves toward lower risk (the minimum-variance point); negative
   surprise moves toward the higher-risk frontier endpoint.
7. Smooth the signed frontier coordinate over five sessions. The primary rule uses a sinusoidal
   kernel; linear and quadratic kernels are run on identical data for comparison.

Weights decided after close on session t are applied to the return on t+1. The backtest begins in
January 2023, uses adjusted closes, rebalances daily, and charges 5 basis points per unit of
turnover. The first 20 observations are an initialization period held at 60/40 because a rolling
covariance estimate is not yet available.

## Broker scope

The research backtest uses adjusted-close data so dividends and splits are represented. IBKR
`TRADES` historical bars are not total-return data, so they are not silently substituted. A
separate paper-account planning script converts the latest target into non-transmitting IBKR order
instructions after checking account mode. It never sends an order.

## Reproducibility

Run `uv run thesispaper all volatility_frontier`, then
`uv run python theses/volatility_frontier/analysis.py`. The second command writes the interpolation
comparison, trade ledger, and thesis-specific figures; rebuild once more to include them in the
paper.
