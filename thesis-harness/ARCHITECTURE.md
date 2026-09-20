# Architecture

`tradebot` is a small, strategy-agnostic trading and backtesting toolkit for Interactive Brokers.

```
strategy/   base (Strategy interface, StrategyContext), constant (fixed target weights)
execution/  runner (periodic rebalance loop), sizer (weights -> whole-share orders)
broker/     base (Broker protocol, Order/Fill/Position/Bar), sim (in-memory), ibkr (ib_async)
risk.py     pre-trade gate: kill switch, per-order notional cap
state/      SQLAlchemy models, best-effort persistence, startup reconcile (Alembic in migrations/)
backtest.py daily-rebalance backtest over Yahoo bars, with FX conversion to the base currency
instruments.py  registry symbol -> currency/exchange/Yahoo ticker (extend with register())
portfolio.py    parse / validate / normalize weights
data/sources/yfinance.py  daily bars and FX from Yahoo
config.py, notify.py      settings from env/.env; Telegram notifications
dashboard/  Streamlit view of NAV, positions, orders
research/   CLIs: backtest, dry_run (no broker), ibkr_check (read-only smoke test)
```

## Runner cycle

1. Skip if the broker is disconnected.
2. Read NAV and positions; ask the strategy for target weights (`TARGET_WEIGHTS` for the
   constant strategy).
3. Convert prices to the base currency, size whole-share orders, drop orders for closed
   markets or symbols with an order already working.
4. Risk-check, place, persist NAV/orders/fills, notify.

Persistence is best-effort: a DB failure is logged and never aborts a cycle.

## Adding a strategy

Implement `Strategy.target_weights(now, ctx) -> dict[str, float]` (see `strategy/base.py`) and
pass it to `run_once`. Register any new symbols in `instruments.py` first.
