# graphics_paper

Figures for the volatility-aware overnight SPY strategy.

```
research/paper_export.py   ->   graphics_paper/data/*.csv   ->   graphics_paper/render.py   ->   figures/*.png + *.pdf
   (needs the IBKR gateway)        (plain CSV, any tool)            (pandas + matplotlib only)
```

## Regenerate

```bash
uv run python research/paper_export.py --months 36      # fetch + compute (gateway up; ~3 min first time, cached after)
uv run python research/paper_export.py --no-ibkr        # recompute from the cached intraday bars only
uv run --group paper python graphics_paper/render.py    # draw the figures
```

`render.py` needs nothing from the trading engine: copy `data/` and `render.py` anywhere with
pandas, numpy and matplotlib and it runs (`--data`, `--out`, `--formats png pdf`).

## The strategy

The portfolio's SPY slice (27% of NAV) belongs to one daily rule. At 15:00 ET (60 minutes before the
close) the model looks at the overnight edge and at volatility: the trailing overnight and daily
variances it already used, plus **today's realized volatility from the open to 15:00** (5-minute
bars, scaled to a full session). Either the **whole slice** is held from the close to the next open,
or SPY is not touched that day. The other nine ETFs follow their normal weights.
A day trades only if the model's sized weight `0.25 * net edge / risk variance` is at least
`min_weight` (0.5, the author's choice, not fitted: see `sensitivity_min_weight.csv`).

## Data files (`data/`)

| File | Rows | Columns |
|---|---|---|
| `equity.csv` | one per date | `date` + one column per strategy, start = 100 |
| `returns.csv` | one per date | `date` + daily total return per strategy |
| `summary.csv` | one per strategy | `strategy, key, sessions, total_return, cagr, volatility, sharpe, max_drawdown` |
| `decisions.csv` | one per decision day | `decision_date, sale_date, traded, raw_weight, weight, mu, sigma_overnight, sigma_daily, sigma_intraday, risk_sigma, intraday_missing, next_overnight_return, slice_return, intraday_var` |
| `sensitivity_min_weight.csv` | one per threshold | `min_weight, trade_fraction, sessions, total_return, cagr, volatility, sharpe, max_drawdown` |
| `sensitivity_cost.csv` | one per cost | `cost_bps` in place of `min_weight`, same metrics |
| `intraday_vol.csv` | one per session | `date, intraday_var, intraday_sigma` (scaled to a full session) |
| `window.csv` | 1 | sample window, counts, and the parameters used |
| `meta.json` | - | sources, parameters and caveats |
| `cache/spy_5min.csv` | one per 5-min bar | raw IBKR bars (`ts` is the bar start, UTC) |

Strategy keys: `vol_aware` (the proposal), `binary_ev` (same, no volatility term, trade whenever
the expected edge is positive), `always` (overnight every day, no model), `cash` (SPY slice idle),
`blend_hold` (SPY held continuously, the earlier portfolio), `classic` (60/40), `spy` (buy & hold).
`traded` is a boolean; `sigma_intraday` is a fraction (0.005 = 0.5% daily-equivalent).
A decision made on `decision_date` earns its return on `sale_date` (the next open).

## Figures (`figures/`)

1. `fig1_equity` cumulative value of the whole portfolio, all strategies
2. `fig2_drawdown` drawdowns
3. `fig3_slice_contribution` what each overnight rule adds versus leaving the SPY slice in cash
4. `fig4_decisions` daily volatility readings, which days were held/skipped, and the rolling share held
5. `fig5_vol_vs_overnight` does morning volatility predict the coming night's return (scatter and quintiles)
6. `fig6_distributions` return distributions of held versus skipped nights
7. `fig7_sensitivity` minimum-weight bar and trading cost (both panels share the same axes)
8. `fig8_summary_table` summary statistics
9. `fig9_rolling_sharpe` rolling 126-session annualized Sharpe ratios for the four principal comparators
10. `fig10_sharpe_difference` histogram of the paired rolling Sharpe difference: volatility-aware minus SPY buy-and-hold

## Caveats

- The overnight leg is computed in USD; FX moves during the hold are ignored (the other holdings do
  carry their currency conversion, into CAD).
- Costs are an all-in round-trip figure in bps, applied only on days with a trade. No tax, cash
  interest, commission minimums or market impact.
- The window is about three years of a rising market. Nothing here is statistically conclusive.
- Daily rebalancing to the target weights is assumed for the non-SPY holdings.
- Sessions without a usable 15:00 reading are skipped, never traded blind (see `intraday_missing`).
- The `min_weight` bar was not fitted; the sensitivity figure shows how little it matters.
