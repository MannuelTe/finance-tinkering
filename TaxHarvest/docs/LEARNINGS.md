# Learnings

## The goal has to be tax savings

The first version compared **loss dollars** with a number described as a tax target. That
mixed units: a \$1 loss does not save \$1 of tax. The planner now accepts a goal in **tax
dollars**, converts it to the loss required at the assumed effective rate, and measures
confidence as the probability of saving at least that amount.

The gain base also has to come from taxable realizations. A price move in an unsold holding
changes future loss capacity; it does not change this year's realized gains. Adding paper
returns to the tax bill made the old sample's reported saving too low.

## Capacity is not a sale

A fixed list of conditional orders needs more loss capacity than the goal in order to hit it
with high confidence. Selling every selected lot whenever it is underwater realizes more
loss than necessary in the scenarios where the market falls. The revised plan selects **maximum
candidate quantities**. At the sale date it ranks the available lots by loss per
replacement-adjusted trading cost, sells up to the loss required for the tax goal, and can
partly fill the final lot. Unused candidate capacity stays unsold.

If the requested goal is infeasible at the chosen confidence, selling every eligible lot is
not a sensible default. The report states the requested goal and the model's reliable upper
bound, then plans for a lower attainable tax-saving goal. The fallback uses 98% of that bound
for a little room against simulation error. It remains a model-dependent estimate, not a
promise of actual savings.

## The operational constraints matter

The rule screen sees across the accounts provided, including scheduled purchases and DRIPs.
The sample's 401(k) purchases of IVV block a taxable VOO sale, and PFE's DRIP blocks PFE.
Missing transactions in another account or a spouse's account can change eligibility. Fund
identity groups are intentionally conservative; the code cannot settle a tax authority's
facts-and-circumstances judgment.

The replacement matters too. Deeply losing single stocks can provide reliable losses, but a
sector ETF is often a weaker match than another broad index fund. A candidate pool that looks
small in market value can still create tracking risk during the replacement window. The
optimizer penalizes that risk, while the report shows the full-pool estimate separately from
the smaller amount expected to be sold.

## Confidence is conditional on the return model

Making **expected** savings equal a goal is not enough: in the worked examples, the old
mean-matching method hit its threshold only about half the time. The calibrated solver sizes
candidate capacity to a chosen confidence, and independent scenario runs check how often it
holds. A stronger rally or higher volatility can still let losing lots recover before sale.
The [results](RESULTS.md) give the updated stress tests and the cost of a more cautious plan.

More simulation scenarios reduce Monte Carlo noise. They do not remove uncertainty in the
return assumptions. The Gaussian hidden Markov model is useful for learning persistent
regimes, but its fitted distribution still needs stress tests. A planning policy that updates
daily as prices, gains, and purchases change remains the main next step.
