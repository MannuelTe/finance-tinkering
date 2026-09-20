from __future__ import annotations

from ib_async import Order as IBOrder
from ib_async import OrderStatus, Stock, Trade

from tradebot.broker.ibkr import IBKRBroker


class _StubIB:
    def __init__(self, trades: list[Trade]) -> None:
        self._trades = trades

    def reqAllOpenOrders(self) -> list[Trade]:
        return self._trades


def _trade(symbol: str, status: str) -> Trade:
    return Trade(
        contract=Stock(symbol, "SMART", "EUR"),
        order=IBOrder(),
        orderStatus=OrderStatus(status=status),
        fills=[],
        log=[],
    )


def test_only_active_orders_count_as_working():
    broker = IBKRBroker()
    broker._ib = _StubIB(
        [
            _trade("EXSA", "Submitted"),
            _trade("XUT", "PreSubmitted"),  # queued while the exchange is closed
            _trade("PAVE", "PendingSubmit"),
            _trade("SPY", "Filled"),
            _trade("TLT", "Cancelled"),
            _trade("IBCF", "Inactive"),
        ]
    )
    assert broker.open_order_symbols() == {"EXSA", "XUT", "PAVE"}


def test_fx_falls_back_when_ibkr_has_no_fx_data():
    class NoFxIB:
        def qualifyContracts(self, *contracts):
            return []  # IDEALPRO pair not available to this account

    broker = IBKRBroker(fx_fallback=lambda currency, base: 1.37 if (currency, base) == ("USD", "CAD") else 0.0)
    broker._ib = NoFxIB()
    assert broker.fx_rate("USD", "CAD") == 1.37
    assert broker.fx_rate("CAD", "CAD") == 1.0


class _SetupIB:
    def __init__(self, accounts: list[str], currency: str = "CAD") -> None:
        self._accounts, self._currency = accounts, currency

    def managedAccounts(self) -> list[str]:
        return self._accounts

    def accountSummary(self):
        return [
            type("Row", (), {"tag": "NetLiquidation", "currency": self._currency, "value": "1"})()
        ]

    def qualifyContracts(self, *contracts):
        for c in contracts:
            c.conId = 1
        return list(contracts)


def _setup_broker(accounts: list[str], monkeypatch, mode: str, currency: str = "CAD") -> IBKRBroker:
    from tradebot import config

    monkeypatch.setattr(config.settings, "ib_mode", mode)
    monkeypatch.setattr(config.settings, "base_currency", "CAD")
    broker = IBKRBroker()
    broker._ib = _SetupIB(accounts, currency)
    return broker


def test_check_setup_accepts_paper_account_in_paper_mode(monkeypatch):
    _setup_broker(["DU1234567"], monkeypatch, "paper").check_setup(["SPY"])


def test_check_setup_refuses_live_account_in_paper_mode(monkeypatch):
    import pytest

    with pytest.raises(RuntimeError, match="not a paper account"):
        _setup_broker(["U1234567"], monkeypatch, "paper").check_setup(["SPY"])


def test_check_setup_refuses_paper_account_in_live_mode(monkeypatch):
    import pytest

    with pytest.raises(RuntimeError, match="is a paper account"):
        _setup_broker(["DU1234567"], monkeypatch, "live").check_setup(["SPY"])


def test_check_setup_refuses_wrong_account_currency(monkeypatch):
    import pytest

    with pytest.raises(RuntimeError, match="BASE_CURRENCY"):
        _setup_broker(["DU1234567"], monkeypatch, "paper", currency="USD").check_setup(["SPY"])


# IBKR's real liquidHours for XUT (Toronto), captured 2026-09-18.
XUT_HOURS = (
    "20260918:0930-20260918:1600;20260919:CLOSED;20260920:CLOSED;"
    "20260921:0930-20260921:1600;20260922:0930-20260922:1600"
)


def _utc(y, mo, d, h, mi):
    from datetime import UTC, datetime

    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_in_session_uses_the_exchange_time_zone():
    from tradebot.broker.ibkr import in_session

    # Friday 2026-09-18, Toronto = US/Eastern = UTC-4 (EDT).
    assert in_session(XUT_HOURS, "US/Eastern", _utc(2026, 9, 18, 14, 0))  # 10:00 ET open
    assert not in_session(XUT_HOURS, "US/Eastern", _utc(2026, 9, 18, 22, 45))  # 18:45 ET closed
    assert not in_session(XUT_HOURS, "US/Eastern", _utc(2026, 9, 18, 13, 29))  # 09:29 ET, pre-open
    assert in_session(XUT_HOURS, "US/Eastern", _utc(2026, 9, 18, 13, 30))  # 09:30 ET, open
    assert not in_session(XUT_HOURS, "US/Eastern", _utc(2026, 9, 18, 20, 0))  # 16:00 ET, closed


def test_in_session_weekend_and_garbage_are_closed():
    from tradebot.broker.ibkr import in_session

    assert not in_session(XUT_HOURS, "US/Eastern", _utc(2026, 9, 19, 15, 0))  # Saturday
    assert not in_session("", "US/Eastern", _utc(2026, 9, 18, 14, 0))
    assert not in_session("nonsense;20260918:xx", "US/Eastern", _utc(2026, 9, 18, 14, 0))
    assert not in_session(XUT_HOURS, "Not/AZone", _utc(2026, 9, 18, 14, 0))
