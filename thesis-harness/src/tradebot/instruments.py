"""Instrument registry.

PURPOSE: map a trading symbol to what the broker and the backtester need to know about it.
INPUTS:  `register()` calls (or edits to `_EXAMPLES`) describing symbol, currency, exchange.
OUTPUTS: `INSTRUMENTS`, a dict symbol -> `Instrument`, used by the IBKR broker (contracts),
         the runner (currency/FX conversion) and the backtester (Yahoo tickers).

To trade another instrument, add it before the broker connects::

    from tradebot.instruments import Instrument, register
    register(Instrument("EXSA", "EUR", primary_exchange="IBIS", yahoo="EXSA.DE"))

`IBKRBroker.check_setup()` re-qualifies every contract at startup and fails loudly on anything
it cannot resolve unambiguously.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    """Everything needed to trade and backtest one symbol. `symbol` is the IBKR symbol and the
    key used everywhere else (weights, positions, orders); `yahoo` is only for backtest data."""

    symbol: str
    currency: str
    exchange: str = "SMART"
    primary_exchange: str | None = None
    yahoo: str | None = None

    @property
    def yahoo_symbol(self) -> str:
        return self.yahoo or self.symbol


# Neutral US-listed examples, quoted in USD.
_EXAMPLES = [
    Instrument("SPY", "USD"),
    Instrument("TLT", "USD"),
    Instrument("GLD", "USD"),
    Instrument("SLV", "USD"),
    Instrument("AGG", "USD"),
]

INSTRUMENTS: dict[str, Instrument] = {i.symbol: i for i in _EXAMPLES}


def register(instrument: Instrument) -> Instrument:
    """Add (or replace) an instrument in the registry and return it."""
    INSTRUMENTS[instrument.symbol] = instrument
    return instrument
