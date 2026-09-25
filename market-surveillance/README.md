# Market Surveillance

Market-surveillance analytics and transaction-reporting controls for equities. The package
combines a pre-announcement event study, Bloomberg-export quality checks, identifier validation,
and reconciliation of internal trades against ARM acknowledgements.

The project is designed as an auditable reference implementation: calculations are deterministic,
inputs are validated at system boundaries, and licensed row-level data stays outside version
control.

## Capabilities

| Area | Capability |
|---|---|
| Surveillance | Market-model abnormal returns and abnormal volume before takeover announcements |
| Controls | Within-stock placebo observations for contextualizing the screen's flag rate |
| Data quality | Completeness and event-date alignment checks for wide Bloomberg exports |
| Reporting | Validation for an equity-focused subset of MiFIR RTS 22 fields |
| Reconciliation | Missing, unexpected, rejected, quantity, and price breaks against ARM acknowledgements |
| Reference data | LEI mod-97, ISIN Luhn, MIC, country, and currency format validation |

## Installation

Python 3.12 or later and [uv](https://docs.astral.sh/uv/) are recommended.

```bash
uv sync
uv run pytest
```

Bloomberg Desktop API access is optional and requires a logged-in Terminal:

```bash
uv sync --extra bloomberg
```

## Command line

Validate a Bloomberg export before running any analysis:

```bash
uv run marketsurv validate-pull data/raw/pilot.csv
```

Run the real-event screen and three within-stock placebo observations per eligible deal:

```bash
uv run marketsurv analyze data/raw/datapull.csv
```

The analysis writes row-level results to `data/cache/event-study-results.csv`. Both `data/raw/`
and `data/cache/` are ignored because they contain licensed or vendor-derived observations.
Use `--help` on the root command or either subcommand for all options.

## Python API

```python
from marketsurv.data.datapull import load_datapull
from marketsurv.surveillance.event_study import pre_event_screen

deals, series = load_datapull("data/raw/datapull.csv")
deal = deals.iloc[0]
stock = series[int(deal.deal_id)]

result = pre_event_screen(stock, stock["mkt"], deal.day0_date)
if result is not None:
    print(result.to_dict())
```

For transaction reporting, construct a `TransactionReport` and pass it to
`marketsurv.reporting.rts22.validate`. Reconciliation is available from
`marketsurv.reporting.reconcile.reconcile`.

## Methodology

For each announcement, the surveillance screen fits a market model over trading days -250 through
-30 and evaluates cumulative abnormal return and log-volume over days -10 through -1. By default,
an observation is flagged when its CAR t-statistic is at least 3.0 and its abnormal-volume z-score
is at least 2.0. The batch workflow repeats the same calculation at earlier placebo dates on the
same security.

A flag is a triage signal, not a finding of market abuse. Rumours, leaks, sector news, corporate
events, stale identifiers, and imperfect announcement timestamps can produce similar patterns.
Results require human review and should be interpreted alongside the placebo rate and source-data
diagnostics.

## Repository layout

```text
src/marketsurv/          reusable package and CLI
tests/                   deterministic unit tests
scripts/                 Bloomberg and compatibility entry points
figures/                 aggregate, redistributable diagnostics
data/raw/                licensed inputs (ignored)
data/cache/              row-level analysis outputs (ignored)
```

## Scope and data handling

- The event study operates on daily prices and volume; it does not infer intent or identify
  participants.
- Order-level behaviours such as spoofing and layering are outside the available data model.
- The RTS 22 validator intentionally covers an equity-focused subset. It is a control aid, not a
  substitute for the current ESMA reporting instructions or ISO 20022 schema validation.
- Bloomberg data must remain under `data/raw/` or `data/cache/`. Only code and aggregate,
  non-identifying diagnostics should be committed.

The repository's private `WIP.md` is ignored by Git and holds experiments, unfinished ideas, and
the resume point for future development.
