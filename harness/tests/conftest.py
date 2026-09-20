from __future__ import annotations

import pytest

from tradebot.broker.sim import SimBroker


@pytest.fixture
def sim_broker() -> SimBroker:
    return SimBroker(starting_cash=100_000.0)


@pytest.fixture(autouse=True)
def _multi_currency_instruments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-USD test instruments (EUR and CAD listings) on top of the default registry."""
    from tradebot.instruments import INSTRUMENTS, Instrument

    monkeypatch.setitem(INSTRUMENTS, "EXSA", Instrument("EXSA", "EUR", primary_exchange="IBIS"))
    monkeypatch.setitem(INSTRUMENTS, "XUT", Instrument("XUT", "CAD", primary_exchange="TSE"))
