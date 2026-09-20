# Status and limitations

Status: infrastructure only (broker, execution, state, risk, backtest, dashboard). Tested
against simulated brokers; the IBKR path is exercised only by unit tests and paper accounts.

Known limitations:

- Not validated for live trading; see SECURITY.md.
- Market orders only; late-fill persistence and cancellation handling are incomplete.
- No automatic FX cash conversion, slippage or commission model; backtests ignore both.
- Target weights come from configuration (`TARGET_WEIGHTS`); there is no dynamic strategy loader.
