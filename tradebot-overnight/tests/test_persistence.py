from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from tradebot.broker.base import Fill, Order
from tradebot.broker.sim import SimBroker
from tradebot.execution.runner import run_once
from tradebot.state.models import Base, NavSnapshot, OrderRecord
from tradebot.state.persistence import record_nav, record_orders_and_fills
from tradebot.strategy.constant import ConstantWeightStrategy

ROOT = Path(__file__).resolve().parent.parent
POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")


@pytest.fixture(scope="session")
def postgres_engine():
    """Real Postgres, schema built by the actual Alembic migration (not create_all), so this also
    proves the migration matches the models. Opt in with TEST_POSTGRES_URL pointing at a
    throwaway database — the tables are truncated between tests."""
    if not POSTGRES_URL:
        pytest.skip("set TEST_POSTGRES_URL to run against Postgres")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": POSTGRES_URL},
        check=True,
    )
    return create_engine(POSTGRES_URL)


@pytest.fixture(params=["sqlite", "postgres"])
def session_factory(request) -> sessionmaker[Session]:
    if request.param == "sqlite":
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        return sessionmaker(engine)

    engine = request.getfixturevalue("postgres_engine")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE orders, fills, nav_snapshots RESTART IDENTITY CASCADE"))
    return sessionmaker(engine)


def test_record_nav(session_factory):
    with session_factory() as s:
        record_nav(s, 1234.5)
        assert s.scalars(select(NavSnapshot)).one().nav == 1234.5


def test_orders_link_to_fills_and_unfilled_stay_submitted(session_factory):
    ts = datetime.now(UTC)
    orders = [Order("TLT", 3.0), Order("XUT", 5.0)]
    fills = [Fill("TLT", 3.0, 500.0, ts)]
    with session_factory() as s:
        record_orders_and_fills(s, orders, fills)
        by_symbol = {o.symbol: o for o in s.scalars(select(OrderRecord))}
        assert by_symbol["TLT"].status == "filled"
        assert by_symbol["TLT"].fills[0].price == 500.0
        assert by_symbol["XUT"].status == "submitted"
        assert by_symbol["XUT"].fills == []


def _broker_with_position() -> SimBroker:
    # Seed a position and a price so the runner has something to rebalance.
    # 10 shares held, target is 11 -> a single 1-share (100 notional) buy, under the risk cap.
    broker = SimBroker(starting_cash=100_000.0)
    broker.set_price("TLT", 100.0)
    broker.place([Order("TLT", 10.0)])
    return broker


def test_run_once_persists_nav_orders_and_fills(session_factory):
    broker = _broker_with_position()
    strategy = ConstantWeightStrategy(weights={"TLT": 0.011})

    run_once(broker, strategy, session_factory)

    with session_factory() as s:
        assert s.scalars(select(NavSnapshot)).one().nav == 100_000.0
        order = s.scalars(select(OrderRecord)).one()
        assert order.symbol == "TLT"
        assert len(order.fills) == 1


def test_failed_writes_do_not_abort_the_cycle():
    """NAV/order records are best-effort: a database that reads fine but cannot commit must not
    stop an order that was already worth placing."""

    class FailingCommit(Session):
        def commit(self):
            raise RuntimeError("db down")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    broker = _broker_with_position()

    run_once(
        broker,
        ConstantWeightStrategy(weights={"TLT": 0.011}),
        sessionmaker(engine, class_=FailingCommit),
    )
    assert broker.positions()[0].qty == 11.0  # the order still went through


def test_runner_never_trades_spy_it_belongs_to_the_overnight_rule():
    """SPY is neither a portfolio target nor counted in positions, so the loop can neither buy
    nor sell it, whatever the weights or the account holds."""
    from tradebot.broker.base import Position

    broker = _broker_with_position()
    broker.set_price("SPY", 500.0)
    broker.place([Order("SPY", 40.0)])  # an overnight holding the runner must leave alone
    run_once(broker, ConstantWeightStrategy(weights={"SPY": 0.6, "TLT": 0.011}))
    holdings = {p.symbol: p.qty for p in broker.positions() if isinstance(p, Position)}
    assert holdings["SPY"] == 40.0  # untouched
    assert holdings["TLT"] == 11.0  # the rest still follows its target
