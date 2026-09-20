from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    """Everything needed to trade and backtest one ETF. `symbol` is the IBKR symbol and the key
    used everywhere else (weights, positions, orders); `yahoo` is only for backtest data."""

    symbol: str
    currency: str
    exchange: str = "SMART"
    primary_exchange: str | None = None
    yahoo: str | None = None

    @property
    def yahoo_symbol(self) -> str:
        return self.yahoo or self.symbol


# IBKR exchange codes: IBIS/IBIS2 = Xetra, LSEETF = London ETF segment, TSE = Toronto. All of
# these were resolved against a paper gateway on 2026-09-18 (IBIS is reported back as IBIS2 for
# some funds, which SMART routing handles). `IBKRBroker.check_setup()` re-qualifies every
# contract at startup and fails loudly on anything it can't resolve unambiguously.
# IBCF (Xetra) does not exist at IBKR; the same fund trades in London as IUSE.
_INSTRUMENTS = [
    # US-listed, USD
    Instrument("SPY", "USD"),
    Instrument("TLT", "USD"),
    # Xetra, EUR
    Instrument("EXSA", "EUR", primary_exchange="IBIS", yahoo="EXSA.DE"),  # STOXX Europe 600
    Instrument("MEEQ", "EUR", primary_exchange="IBIS", yahoo="MEEQ.DE"),  # MSCI Europe Equal Wt
    Instrument("EXH1", "EUR", primary_exchange="IBIS", yahoo="EXH1.DE"),  # STOXX 600 Oil & Gas
    Instrument("XDEW", "EUR", primary_exchange="IBIS", yahoo="XDEW.DE"),  # S&P 500 Equal Wt
    # London ETF segment
    Instrument("PAVE", "USD", primary_exchange="LSEETF", yahoo="PAVE.L"),  # US infrastructure
    Instrument("DTLE", "EUR", primary_exchange="LSEETF", yahoo="DTLE.L"),  # 20+y UST EUR-hedged
    Instrument("IUSE", "EUR", primary_exchange="LSEETF", yahoo="IUSE.L"),  # S&P 500 EUR-hedged
    # Toronto, CAD
    Instrument("XUT", "CAD", primary_exchange="TSE", yahoo="XUT.TO"),  # Canadian utilities
]

INSTRUMENTS: dict[str, Instrument] = {i.symbol: i for i in _INSTRUMENTS}
