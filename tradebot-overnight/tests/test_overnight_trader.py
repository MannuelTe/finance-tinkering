from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tradebot import config, overnight
from tradebot.broker.base import Bar, Fill, Order, Position, Session
from tradebot.execution.overnight_runner import OvernightTrader
from tradebot.state.models import Base, OvernightDay

ET = ZoneInfo("America/New_York")
MONDAY = date(2026, 9, 21)
OPEN = datetime(2026, 9, 21, 9, 30, tzinfo=ET)
CLOSE = datetime(2026, 9, 21, 16, 0, tzinfo=ET)


class FakeBroker:
    """Enough of an IBKR broker to drive the daily lifecycle."""

    def __init__(self) -> None:
        self.placed: list[Order] = []
        self.filled: dict[str, float] = {}
        self.market_open = False
        self.weekend = False
        self.connected = True
        self.fail_place = False

    def is_connected(self) -> bool:
        return self.connected

    def nav(self) -> float:
        return 250_000.0

    def positions(self) -> list[Position]:
        return []

    def account(self) -> str:
        return "DU1234567"

    def price(self, symbol: str) -> float | None:
        return 750.0  # USD

    def fx_rate(self, currency: str, base: str) -> float:
        return 1.4  # CAD per USD -> 1,050 CAD per share

    def is_market_open(self, symbol: str) -> bool:
        return self.market_open

    def open_order_symbols(self) -> set[str]:
        return set()

    def bars(self, symbol: str, lookback_days: int) -> list[Bar]:
        return []

    def session_today(self, symbol: str, now: datetime) -> Session | None:
        return None if self.weekend else Session(OPEN, CLOSE)

    def filled_qty(self, ref: str) -> float:
        return self.filled.get(ref, 0.0)

    def place(self, orders: list[Order]) -> list[Fill]:
        if self.fail_place:
            raise ConnectionError("gateway went away mid-call")
        self.placed.extend(orders)
        return []


def _bars(direction: float, n: int = 40) -> pd.DataFrame:
    """direction > 0: a steady positive overnight drift (model says trade); < 0: it says cash."""
    close = 100 + np.cumsum(np.full(n, 0.05))
    jitter = np.tile([0.0, 0.0002], n)[:n]
    open_ = np.r_[100, close[:-1]] * (1 + direction * 0.002 + jitter)
    return pd.DataFrame({"open": open_, "close": close}, index=pd.bdate_range("2026-06-01", periods=n))


def _intraday(sigma: float, seed: int = 3, bars: int = 78) -> pd.DataFrame:
    """Today's 5-minute bars (09:30 ET onward), i.i.d. log returns of std `sigma` per bar."""
    stamps = pd.date_range(OPEN.astimezone(UTC), periods=bars, freq="5min")
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, sigma, bars)))
    return pd.DataFrame({"ts": stamps, "open": np.r_[100.0, close[:-1]], "close": close})


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(config.settings, "kill_switch", False)
    monkeypatch.setattr(config.settings, "max_notional", Decimal(1_000_000))
    monkeypatch.setattr(config.settings, "base_currency", "CAD")
    monkeypatch.setattr(config.settings, "overnight_min_weight", 0.5)
    monkeypatch.setattr(config.settings, "overnight_decision_jitter_minutes", 0)
    monkeypatch.setattr(config.settings, "overnight_price_buffer", 0.01)


def _trader(broker, db, direction=1.0, seed=7, sigma=0.0005, weight=0.27):
    """calm intraday (sigma per 5-min bar 0.0005) unless told otherwise; SPY slice = `weight`."""
    cfg = overnight.OvernightConfig(window=5, cost_bps=0, binary=True, min_weight=0.5)
    return OvernightTrader(
        broker, db, lambda: _bars(direction), lambda: _intraday(sigma), cfg,
        spy_weight=weight, rng=random.Random(seed),
    )


def _row(db, day: date = MONDAY) -> OvernightDay:
    with db() as s:
        row = s.get(OvernightDay, day)
        assert row is not None
        return row


def _decision_at(db) -> datetime:
    return _row(db).decision_at.replace(tzinfo=UTC)


REF = f"overnight:{MONDAY.isoformat()}:"


# ---- schedule ----------------------------------------------------------------------------


def test_decision_is_at_exactly_15_00_et_and_stored(db):
    broker = FakeBroker()
    _trader(broker, db).tick(OPEN + timedelta(hours=1))
    assert _decision_at(db) == CLOSE.astimezone(UTC) - timedelta(minutes=60)
    assert _decision_at(db).astimezone(ET).strftime("%H:%M") == "15:00"


def test_optional_jitter_is_drawn_once_inside_15_00_to_15_30_and_survives_restarts(db, monkeypatch):
    monkeypatch.setattr(config.settings, "overnight_decision_jitter_minutes", 30)
    broker = FakeBroker()
    _trader(broker, db).tick(OPEN + timedelta(hours=1))
    first = _decision_at(db)
    start = CLOSE.astimezone(UTC) - timedelta(minutes=60)
    assert start <= first <= start + timedelta(minutes=30)
    _trader(broker, db, seed=99).tick(OPEN + timedelta(hours=2))  # a fresh process, another seed
    assert _decision_at(db) == first


def test_decision_window_moves_with_an_early_close():
    early_close = datetime(2026, 11, 27, 13, 0, tzinfo=ET)
    start, end = overnight.decision_window(early_close)
    assert (start.hour, start.minute, end.hour, end.minute) == (12, 0, 12, 45)
    assert overnight.decision_time(early_close).hour == 12  # the fixed daily instant follows too


def test_draws_cover_the_whole_window_and_stay_inside_it():
    rng = random.Random(1)
    draws = [overnight.draw_decision_time(CLOSE, rng) for _ in range(2000)]
    start, end = overnight.decision_window(CLOSE)
    assert all(start <= d <= end for d in draws)
    assert min(draws) < start + timedelta(minutes=2) and max(draws) > end - timedelta(minutes=2)


def test_no_session_no_row(db):
    broker = FakeBroker()
    broker.weekend = True
    _trader(broker, db).tick(OPEN + timedelta(hours=6))
    with db() as s:
        assert s.scalars(select(OvernightDay)).all() == []
    assert broker.placed == []


def test_disconnected_broker_does_nothing(db):
    broker = FakeBroker()
    broker.connected = False
    _trader(broker, db).tick(CLOSE - timedelta(minutes=30))
    assert broker.placed == []


# ---- the binary decision -----------------------------------------------------------------


def test_nothing_happens_before_the_decision_moment(db):
    broker = FakeBroker()
    trader = _trader(broker, db)
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) - timedelta(seconds=1))
    assert broker.placed == [] and _row(db).decided_at is None


def test_yes_places_exactly_one_sized_moc_entry(db):
    broker = FakeBroker()
    trader = _trader(broker, db)
    trader.tick(OPEN + timedelta(hours=1))
    at = _decision_at(db)
    trader.tick(at)
    trader.tick(at + timedelta(seconds=30))
    _trader(broker, db).tick(at + timedelta(seconds=60))  # a "restart": brand-new process
    trader.tick(at + timedelta(seconds=90))
    assert len(broker.placed) == 1
    entry = broker.placed[0]
    # the WHOLE SPY slice: 27% of 250,000 CAD = 67,500; / (750 USD * 1.4 * 1.01) = 63.65 -> 63
    assert (entry.symbol, entry.qty, entry.order_type, entry.tif) == ("SPY", 63.0, "MOC", "DAY")
    assert entry.transmit and entry.account == "DU1234567" and entry.ref == REF + "entry"
    row = _row(db)
    assert (row.action, row.qty, row.entry_status) == ("PLAN_BUY_CLOSE", 63, "submitted")


def test_no_places_nothing_and_is_recorded(db):
    broker = FakeBroker()
    trader = _trader(broker, db, direction=-1.0)
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) + timedelta(seconds=5))
    assert broker.placed == []
    assert _row(db).action == "STAY_CASH"


def test_a_missed_window_places_nothing_even_if_the_signal_says_yes(db):
    broker = FakeBroker()
    _trader(broker, db).tick(CLOSE - timedelta(minutes=5))  # first look is after the MOC cutoff
    assert broker.placed == [] and _row(db).action == "MISSED"


def test_data_failure_is_retried_until_it_works(db):
    broker = FakeBroker()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("bars unavailable")
        return _bars(1.0)

    trader = OvernightTrader(
        broker, db, flaky, lambda: _intraday(0.0005),
        overnight.OvernightConfig(window=5, cost_bps=0, binary=True, min_weight=0.5), spy_weight=0.27,
    )
    trader.tick(OPEN + timedelta(hours=1))
    at = _decision_at(db)
    for k in range(4):
        trader.tick(at + timedelta(seconds=30 * k))
    assert len(broker.placed) == 1 and calls["n"] == 3


def test_kill_switch_blocks_the_entry(db, monkeypatch):
    monkeypatch.setattr(config.settings, "kill_switch", True)
    broker = FakeBroker()
    trader = _trader(broker, db)
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) + timedelta(seconds=1))
    assert broker.placed == [] and _row(db).entry_status == "rejected"


def test_a_tiny_slice_means_no_trade_not_a_zero_share_order(db):
    broker = FakeBroker()
    trader = _trader(broker, db, weight=0.001)  # 0.1% of 250k = 250 CAD < one share
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) + timedelta(seconds=1))
    assert broker.placed == [] and _row(db).action == "STAY_CASH"


def test_unknown_placement_outcome_is_never_retried(db):
    broker = FakeBroker()
    broker.fail_place = True
    trader = _trader(broker, db)
    trader.tick(OPEN + timedelta(hours=1))
    at = _decision_at(db)
    trader.tick(at + timedelta(seconds=1))
    assert _row(db).entry_status == "submitting"  # intent was persisted before the call
    broker.fail_place = False
    for k in range(1, 6):
        trader.tick(at + timedelta(seconds=30 * k))
    assert broker.placed == []  # a human must check IBKR; the bot never guesses


# ---- entry fill -> exit ------------------------------------------------------------------


def _entered(db, broker):
    trader = _trader(broker, db)
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) + timedelta(seconds=1))
    assert len(broker.placed) == 1
    return trader


def test_exit_waits_for_a_confirmed_fill_and_never_goes_out_with_the_entry(db):
    broker = FakeBroker()
    trader = _entered(db, broker)
    assert [o.order_type for o in broker.placed] == ["MOC"]  # no exit alongside the entry
    trader.tick(CLOSE + timedelta(minutes=1))  # closed, but nothing confirmed filled yet
    assert len(broker.placed) == 1

    broker.filled[REF + "entry"] = 9.0
    trader.tick(CLOSE + timedelta(minutes=2))
    assert len(broker.placed) == 2
    exit_order = broker.placed[1]
    assert (exit_order.qty, exit_order.order_type, exit_order.tif) == (-9.0, "MKT", "OPG")
    assert exit_order.ref == REF + "exit" and exit_order.transmit
    trader.tick(CLOSE + timedelta(minutes=3))  # never a second exit
    assert len(broker.placed) == 2


def test_exit_sells_only_the_shares_that_actually_filled(db):
    broker = FakeBroker()
    trader = _entered(db, broker)
    broker.filled[REF + "entry"] = 4.0  # partial MOC fill
    trader.tick(CLOSE + timedelta(minutes=2))
    assert broker.placed[1].qty == -4.0 and _row(db).entry_filled == 4.0


def test_unfilled_entry_never_produces_an_exit(db):
    broker = FakeBroker()
    trader = _entered(db, broker)
    trader.tick(CLOSE + timedelta(minutes=45))
    assert len(broker.placed) == 1 and _row(db).entry_status == "unfilled"


def test_opg_exit_is_escalated_to_market_if_the_open_did_not_fill_it(db):
    broker = FakeBroker()
    trader = _entered(db, broker)
    broker.filled[REF + "entry"] = 9.0
    trader.tick(CLOSE + timedelta(minutes=2))  # OPG exit submitted
    next_open = OPEN + timedelta(days=1)

    broker.market_open = True
    broker.session_today = lambda symbol, now: Session(next_open, next_open + timedelta(hours=6.5))
    trader.tick(next_open + timedelta(minutes=2))  # too early to escalate
    assert len(broker.placed) == 2
    broker.filled[REF + "exit"] = 3.0  # partly filled at the open
    trader.tick(next_open + timedelta(minutes=6))
    late = broker.placed[2]
    assert (late.qty, late.order_type, late.tif, late.ref) == (-6.0, "MKT", "DAY", REF + "late")
    trader.tick(next_open + timedelta(minutes=7))
    assert len(broker.placed) == 3  # escalate once only
    broker.filled[REF + "late"] = 6.0
    trader.tick(next_open + timedelta(minutes=8))
    assert _row(db).exit_status == "filled" and _row(db).exit_filled == 9.0


def test_process_down_overnight_exits_with_a_market_order_not_opg(db):
    broker = FakeBroker()
    trader = _entered(db, broker)
    broker.filled[REF + "entry"] = 9.0
    broker.market_open = True  # first look is after the next open
    trader.tick(CLOSE + timedelta(hours=18))
    assert broker.placed[1].tif == "DAY" and broker.placed[1].qty == -9.0


def test_kill_switch_never_blocks_an_exit(db, monkeypatch):
    broker = FakeBroker()
    trader = _entered(db, broker)
    broker.filled[REF + "entry"] = 9.0
    monkeypatch.setattr(config.settings, "kill_switch", True)
    trader.tick(CLOSE + timedelta(minutes=2))
    assert len(broker.placed) == 2 and broker.placed[1].qty == -9.0


# ---- the volatility rule at 15:00 ---------------------------------------------------------


def test_a_stormy_morning_skips_the_day_even_though_the_overnight_edge_is_positive(db):
    broker = FakeBroker()
    trader = _trader(broker, db, sigma=0.01)  # violent 5-minute bars -> huge intraday variance
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) + timedelta(seconds=1))
    row = _row(db)
    assert broker.placed == [] and row.action == "STAY_CASH"
    assert "raw_weight=0.0" in row.note and "min_weight=0.5" in row.note  # the reason is on record


def test_a_calm_morning_with_the_same_edge_trades(db):
    broker = FakeBroker()
    trader = _trader(broker, db, sigma=0.0003)
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) + timedelta(seconds=1))
    assert len(broker.placed) == 1 and "sigma_i=" in _row(db).note


def test_only_bars_completed_by_15_00_are_used_so_a_late_tick_cannot_see_more(db):
    """The afternoon crashes after 15:00. A restart at 15:20 must still decide on the 15:00
    picture, exactly as the backtest defines it."""
    def crash_after_3pm() -> pd.DataFrame:
        bars = _intraday(0.0003)
        late = bars.ts >= CLOSE.astimezone(UTC) - timedelta(minutes=60)
        bars.loc[late, "close"] = bars.loc[late, "close"] * 5
        return bars

    broker = FakeBroker()
    cfg = overnight.OvernightConfig(window=5, cost_bps=0, binary=True, min_weight=0.5)
    trader = OvernightTrader(broker, db, lambda: _bars(1.0), crash_after_3pm, cfg, spy_weight=0.27)
    trader.tick(OPEN + timedelta(hours=1))
    trader.tick(_decision_at(db) + timedelta(minutes=20))  # a delayed tick, still before the cutoff
    assert len(broker.placed) == 1  # the post-15:00 crash was invisible


def test_too_few_intraday_bars_means_retry_then_missed_never_a_blind_trade(db):
    broker = FakeBroker()
    cfg = overnight.OvernightConfig(window=5, cost_bps=0, binary=True, min_weight=0.5)
    trader = OvernightTrader(broker, db, lambda: _bars(1.0), lambda: _intraday(0.0003).iloc[:20], cfg, spy_weight=0.27)
    trader.tick(OPEN + timedelta(hours=1))
    at = _decision_at(db)
    for k in range(4):
        trader.tick(at + timedelta(seconds=30 * k))
    assert broker.placed == [] and _row(db).decided_at is None  # still waiting for data
    trader.tick(CLOSE - timedelta(minutes=5))  # the MOC cutoff passes
    assert broker.placed == [] and _row(db).action == "MISSED"
