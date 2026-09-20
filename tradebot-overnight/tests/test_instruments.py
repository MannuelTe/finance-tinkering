from __future__ import annotations

import pytest

from tradebot.broker.ibkr import contract_for
from tradebot.instruments import INSTRUMENTS
from tradebot.portfolio import CLASSIC, HEDGED_EQUIVALENT, SLEEVE, blended_weights


def test_every_portfolio_symbol_is_a_registered_instrument():
    assert set(blended_weights()) <= set(INSTRUMENTS)


def test_blended_weights_sum_to_one_and_hedge_carve_out():
    w = blended_weights()
    assert sum(w.values()) == pytest.approx(1.0)
    # 5% of the whole portfolio moves into hedged share classes, keeping the 60/40 ratio.
    hedged = w["IUSE"] + w["DTLE"]
    assert hedged == pytest.approx(0.05)
    assert w["IUSE"] / w["DTLE"] == pytest.approx(CLASSIC["SPY"] / CLASSIC["TLT"])
    assert w["SPY"] == pytest.approx(0.30 - w["IUSE"])
    assert w["TLT"] == pytest.approx(0.20 - w["DTLE"])


def test_no_hedge_reduces_to_sleeve_plus_classic():
    w = blended_weights(hedge_share=0.0)
    assert set(w) == set(SLEEVE) | set(CLASSIC)
    assert w["SPY"] == pytest.approx(0.30)
    assert not set(HEDGED_EQUIVALENT.values()) & set(w)


def test_hedge_larger_than_classic_share_is_rejected():
    with pytest.raises(ValueError):
        blended_weights(hedge_share=0.6)


def test_contract_uses_registry_exchange_and_currency():
    xetra = contract_for("EXSA")
    assert (xetra.symbol, xetra.currency, xetra.primaryExchange) == ("EXSA", "EUR", "IBIS")
    tsx = contract_for("XUT")
    assert (tsx.currency, tsx.primaryExchange) == ("CAD", "TSE")
    us = contract_for("SPY")
    assert (us.exchange, us.currency) == ("SMART", "USD")


def test_unregistered_symbol_has_a_clear_error():
    with pytest.raises(KeyError, match="INSTRUMENTS"):
        contract_for("NOPE")
