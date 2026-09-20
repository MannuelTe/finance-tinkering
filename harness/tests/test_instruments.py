from __future__ import annotations

import pytest

from tradebot.broker.ibkr import contract_for
from tradebot.instruments import INSTRUMENTS, Instrument, register
from tradebot.portfolio import normalize_weights, parse_weights, validate_weights


def test_default_examples_are_registered():
    assert {"SPY", "TLT", "AGG"} <= set(INSTRUMENTS)


def test_register_adds_instrument_and_contract_uses_it(monkeypatch):
    monkeypatch.setattr("tradebot.instruments.INSTRUMENTS", INSTRUMENTS)
    monkeypatch.delitem(INSTRUMENTS, "EXSA")  # restored by monkeypatch after the test
    register(Instrument("EXSA", "EUR", primary_exchange="IBIS", yahoo="EXSA.DE"))
    c = contract_for("EXSA")
    assert (c.symbol, c.currency, c.primaryExchange) == ("EXSA", "EUR", "IBIS")
    assert INSTRUMENTS["EXSA"].yahoo_symbol == "EXSA.DE"


def test_us_contract_defaults_to_smart_usd():
    us = contract_for("SPY")
    assert (us.exchange, us.currency) == ("SMART", "USD")


def test_unregistered_symbol_has_a_clear_error():
    with pytest.raises(KeyError, match="INSTRUMENTS"):
        contract_for("NOPE")


def test_parse_validate_normalize_weights():
    w = parse_weights("SPY:0.6, TLT:0.4")
    assert w == {"SPY": 0.6, "TLT": 0.4}
    assert validate_weights(w) == w
    assert normalize_weights({"A": 1, "B": 3}) == pytest.approx({"A": 0.25, "B": 0.75})
    with pytest.raises(ValueError):
        validate_weights({"A": 0.7, "B": 0.5})
    with pytest.raises(ValueError):
        validate_weights({"A": -0.1})
    with pytest.raises(ValueError):
        parse_weights("SPY")
