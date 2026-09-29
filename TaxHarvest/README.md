# TaxHarvest

TaxHarvest helps plan which losing tax lots to sell on a chosen date and what to buy in their
place. It looks for the smallest set of conditional sales likely to reach a loss target, while
screening for [US wash sales][us-rules] and [Canadian superficial losses][ca-rules].

I built it from Switzerland, where [private gains on securities are generally untaxed][ch-rules]
and private capital losses are not deductible. That makes Switzerland a useful control: for a
private investor, the engine should recommend no tax-loss harvest. The actual planning problem
is for US and Canadian investors, who need to weigh the value of a loss against repurchase rules
and the risk that a position recovers before the sale.

The portfolios and market assumptions here are illustrative. This is a research project, not a
trading or tax recommendation.

## Try it

From `TaxHarvest/`, use Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run --group dev pytest

# Run the sample portfolio under US and Swiss rules (about 10 minutes).
uv run python scripts/run_sample.py

# Run one of the four worked examples quickly.
uv run python scripts/th.py examples --only canada --quick
```

To analyse your own CSV:

```bash
uv run python scripts/th.py run data/us_portfolio.csv \
    --planned data/us_portfolio_planned.csv \
    --as-of 2026-09-24 --jurisdiction US \
    --realized-gains 15000 --confidence 0.9 --horizon-days 40
```

A portfolio CSV needs `account,ticker,shares,cost_basis,acquired,price`; `drip` is optional. A
planned-purchases CSV uses `ticker,on,account`. Use `uv run python scripts/th.py interactive` to
enter lots by hand, or `uv run python scripts/th.py examples` to run all four examples (about 45
minutes).

The CLI writes trade decisions (`trades.csv`), a summary (`summary.json`), charts, and
animations to `out/` by default. The worked examples and sample go to `figures/`.

## The sample portfolio: one book, two tax systems

The [sample portfolio](data/sample_portfolio.csv) is a fictional \$468k book dated 2026-09-28,
with 19 taxable lots, a 401(k), and a Roth IRA. It starts with \$23.6k of unrealised losses and
\$18k of gains already realised. [Planned 401(k) purchases](data/sample_portfolio_planned.csv)
and a dividend reinvestment plan (DRIP) matter because a purchase can disallow a loss.

The default US target is **\$5,165 of losses**: the assumed 23.8% tax rate times expected gains.
At 90% required confidence, the engine selects \$25,534 of holdings and estimates \$8,574 of
harvested losses and \$1,463 of tax savings this year. Its three conditional sales for 2026-11-25
are:

| Sell if still below cost basis | Buy instead | Expected loss |
|---|---|---:|
| 400 INTC | XLK | \$3,548 |
| 180 NKE | XLY | \$4,283 |
| 38 of 120 DIS | XLC | \$743 |

The screen also blocks VOO because scheduled 401(k) purchases of IVV track the same index, and
PFE because its DRIP is on. Together those lots hold \$4,440 of unrealised losses. The plan says
when the sold securities may be bought back across all accounts.

A larger target changes the answer sharply. To offset **all** expected gains, the book would
need \$21,702 of losses; even selling every eligible losing lot reaches that amount in only 32.8%
of simulated scenarios. The engine reports that the 90% goal is infeasible. Under the Swiss
private investor rules, the target and plan are both zero.

![Selected lots and simulated losses for the sample portfolio](figures/sample/plan.png)

The plan reached 90.0% confidence across 10 fresh simulation runs. It fell to 81.1% when
volatility was 50% higher than assumed and 83.2% in a strong rally. A more cautious version
improved those figures, but selected \$41.5k of holdings instead of \$25.5k. See
[results](docs/RESULTS.md) for the full comparisons and [learnings](docs/LEARNINGS.md) for what
changed during the project.

## How the planner works

For each lot, TaxHarvest simulates prices on a chosen future sale date. It counts a loss only if
the lot is below its cost basis then; otherwise the conditional order does not sell. The
optimiser chooses fractions of eligible lots to minimise the value sold, with a penalty for
replacements that track the originals poorly. Its main constraint is:

```math
\mathbb{P}(\text{harvested loss} \ge \text{target}) \ge \text{required confidence}
```

By default, the target is the assumed tax rate multiplied by expected gains, including gains
already realised and the portfolio's expected return over the horizon. `--target offset` instead
asks for losses equal to **all** expected gains; `--target 5000` sets a fixed loss amount. The
default confidence is 90%, and the default horizon is 40 trading days.

The default `calibrated` solver adjusts a convex approximation until its simulated plan reaches
the requested confidence. A simple plan built around **expected** losses reaches the target only
about half the time in the worked examples. `mean`, `cvar`, and `milp` are available for
comparison; their trade-offs are in [results](docs/RESULTS.md).

### Rules and replacements

The screen checks taxable status, recent and planned purchases of the same security or index
group, purchases in other accounts, and DRIPs. It then chooses a correlated replacement from a
different group and gives a buy-back date. For US and Canadian sales, the model uses a 30-day
window around the sale; its grouping of funds tracking the same index is intentionally
conservative and editable.

The screen only knows about accounts and purchases you provide. In particular, enter relevant
spouse accounts, retirement accounts, employer plans, and scheduled contributions before relying
on its output. The simplified rules are described in
[`washsale.py`](src/taxharvest/washsale.py).

### Return assumptions

The default factor model covers broad markets and sectors. Its parameters in
[`assets.csv`](src/taxharvest/assets.csv) are illustrative, not fitted estimates. Pass
`--history prices.csv` to fit a persistent market-regime model to daily prices instead.
Student-t and bootstrap models are used for stress tests. The [results](docs/RESULTS.md) show
how the plan changes when those assumptions are wrong.

## Limits

- Tax is represented by one effective rate. The model does not implement US short-term/long-term
  netting or every Canadian tax edge case, and it does not count losses above this year's gains
  as immediate savings.
- The plan uses one future sale date. It does not re-plan as prices and account activity change.
- Example prices, cost bases, and return parameters are made up. Replacement similarity is a
  modelling judgement, not a determination by a tax authority.

Source code is in [`src/taxharvest/`](src/taxharvest/), example inputs in [`data/`](data/), and
generated figures in [`figures/`](figures/).

[us-rules]: https://www.irs.gov/publications/p550
[ca-rules]: https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/capital-losses-deductions.html/1000
[ch-rules]: https://www.estv.admin.ch/dam/estv/en/dokumente/estv/steuersystem/schweizer-steuersystem/ch-steuersystem.pdf.download.pdf/ch-steuersystem.pdf
