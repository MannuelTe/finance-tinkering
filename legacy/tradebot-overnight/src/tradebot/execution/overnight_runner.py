"""Daily overnight trade for the portfolio's SPY slice.

The SPY slice (its target weight, 27% of NAV) is managed only by this rule. Every trading day, 60
minutes before that day's actual close (15:00 ET normally, 12:00 on a 13:00 early close), the
model looks at the overnight edge and at volatility: the overnight and daily terms it already
used, plus today's realized intraday volatility from the open up to that moment. It answers
either "hold the WHOLE slice overnight" or "do nothing with SPY today" (binary: the sized
weight, with today's volatility in the risk term, must be at least `overnight_min_weight`).
The decision instant is stored, so a restart never redraws it (an optional random delay of up
to `overnight_decision_jitter_minutes` can be configured; default none). If the answer is yes:

  entry  BUY  MOC   placed at the decision moment, sized to the SPY slice with a price buffer
  exit   SELL OPG   placed only after the entry is CONFIRMED filled by the broker's executions,
                    never alongside the entry; a plain market sell if the open is already here

Safety properties:
  * Every order is preceded by a 'submitting' status in the database, so a crash or restart can
    never place the same order twice (an unknown outcome is left for a human, never retried).
  * The kill switch and per-order cap gate the entry. Exits are never blocked: they cut risk.
  * If the process is down through the decision window the day is recorded MISSED, and no order
    is ever placed after the closing-auction cutoff.
  * The exit is escalated to a market sell if the opening auction did not fill it.
  * The portfolio runner never trades SPY at all, so the two loops cannot fight over it.

Runs as its own process (own IBKR client id) so the 5-minute portfolio loop is unaffected.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import math
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from tradebot import overnight
from tradebot.broker.base import Broker, Order, Session
from tradebot.broker.ibkr import IBKRBroker
from tradebot.config import settings
from tradebot.data.sources.ibkr import download_daily_bars, fetch_intraday_bars
from tradebot.instruments import INSTRUMENTS
from tradebot.notify import notify
from tradebot.portfolio import blended_weights
from tradebot.risk import check_orders
from tradebot.state.models import OvernightDay
from tradebot.state.persistence import record_orders_and_fills

logger = logging.getLogger(__name__)

SYMBOL = "SPY"
TICK_SECONDS = 30
# How long after the close a MOC entry may take to show up in the executions, and how long after
# the open before an unfilled opening-auction exit is escalated to a market order.
ENTRY_CONFIRM_GRACE = timedelta(minutes=30)
EXIT_ESCALATE_AFTER_OPEN = timedelta(minutes=5)

ACTIVE_ENTRY = ("submitted", "filled")
ACTIVE_EXIT = ("none", "submitted", "escalated")


class OvernightBroker(Broker, Protocol):
    def account(self) -> str: ...
    def session_today(self, symbol: str, now: datetime) -> Session | None: ...
    def filled_qty(self, ref: str) -> float: ...


BarsFn = Callable[[], pd.DataFrame]
IntradayFn = Callable[[], pd.DataFrame]  # today's 5-minute bars, columns ts/open/close


def _aware(moment: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat those as UTC (we only ever store UTC)."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def ibkr_bars(broker: IBKRBroker) -> BarsFn:
    """Completed daily sessions through yesterday, validated for the model."""

    def fetch() -> pd.DataFrame:
        frame = download_daily_bars(broker.ib, SYMBOL, "1 Y")
        bars = frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")[["open", "close"]]
        return overnight.validate_bars(bars)

    return fetch


def default_config() -> overnight.OvernightConfig:
    return overnight.OvernightConfig(binary=True, min_weight=settings.overnight_min_weight)


def ibkr_intraday(broker: IBKRBroker) -> IntradayFn:
    """The current session's 5-minute bars so far (the last one may still be forming; the model
    only uses bars that completed before the decision instant)."""

    def fetch() -> pd.DataFrame:
        return fetch_intraday_bars(broker.ib, SYMBOL, "1 D")

    return fetch


class OvernightTrader:
    def __init__(
        self,
        broker: OvernightBroker,
        session_factory: Callable[[], DbSession],
        bars_fn: BarsFn,
        intraday_fn: IntradayFn,
        config: overnight.OvernightConfig | None = None,
        symbol: str = SYMBOL,
        spy_weight: float | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.broker = broker
        self.session_factory = session_factory
        self.bars_fn = bars_fn
        self.intraday_fn = intraday_fn
        self.config = config or default_config()
        self.symbol = symbol
        # The position size is the portfolio's whole SPY slice, as a fraction of NAV.
        self.spy_weight = blended_weights()[symbol] if spy_weight is None else spy_weight
        self.rng = rng

    # ------------------------------------------------------------------ public

    def tick(self, now: datetime) -> None:
        """One scheduling step. Safe to call as often as you like: every action is guarded by
        the stored day record."""
        if not self.broker.is_connected():
            logger.warning("overnight: broker not connected; skipping")
            return
        with self.session_factory() as db:
            self._entry(db, now)
            for row in db.scalars(
                select(OvernightDay).where(
                    OvernightDay.entry_status.in_(ACTIVE_ENTRY),
                    OvernightDay.exit_status.in_(ACTIVE_EXIT),
                )
            ).all():
                self._advance(db, row, now)

    # ------------------------------------------------------------------ entry

    def _entry(self, db: DbSession, now: datetime) -> None:
        session = self.broker.session_today(self.symbol, now)
        if session is None:
            return  # weekend or holiday

        row = db.get(OvernightDay, session.local_date)
        if row is None:
            decision_at = overnight.decision_time(session.end)
            jitter = settings.overnight_decision_jitter_minutes
            if jitter > 0:  # optional random delay, never beyond the MOC cutoff
                jitter = min(jitter, 45)
                decision_at += timedelta(seconds=(self.rng or random.SystemRandom()).randint(0, jitter * 60))
            row = OvernightDay(
                trade_date=session.local_date,
                symbol=self.symbol,
                decision_at=decision_at.astimezone(UTC),
                close_at=session.end.astimezone(UTC),
            )
            db.add(row)
            db.commit()
            logger.info("overnight %s: decision drawn for %s", row.trade_date, decision_at)
        if row.decided_at is not None:
            return

        cutoff = session.end - overnight.MOC_CUTOFF_BEFORE_CLOSE
        if now >= cutoff:
            self._finish(db, row, now, "MISSED", "decision window passed without a decision")
            notify(f"overnight {row.trade_date}: MISSED (no decision before the MOC cutoff)")
            return
        if now < _aware(row.decision_at):
            return
        self._decide(db, row, session, now)

    def _decide(self, db: DbSession, row: OvernightDay, session: Session, now: datetime) -> None:
        try:
            # Volatility from the open up to the decision instant, using only bars that had
            # completed by then: identical to how the backtest measures it, so a late tick
            # (restart) cannot see more of the session than 15:00 would have.
            intraday_var = overnight.intraday_variance(
                self.intraday_fn(), session.start, session.end, _aware(row.decision_at)
            )
            if intraday_var is None:
                raise ValueError("not enough intraday bars up to the decision time")
            signal = overnight.next_signal(self.bars_fn(), self.config, intraday_var)
        except Exception:
            # Data trouble is retried on the next tick until the cutoff; nothing has been sent.
            logger.exception("overnight %s: signal failed; will retry", row.trade_date)
            return

        note = (
            f"mu={signal['mu']:.6f} sigma_o={signal['sigma_overnight']:.6f} "
            f"sigma_d={signal['sigma_daily']:.6f} sigma_i={signal['sigma_intraday']:.6f} "
            f"raw_weight={signal['raw_weight']:.3f} min_weight={self.config.min_weight} "
            f"history_through={signal['history_through']}"
        )
        if signal["action"] != "PLAN_BUY_CLOSE":
            self._finish(db, row, now, "STAY_CASH", note)
            logger.info("overnight %s: stay in cash (%s)", row.trade_date, note)
            return

        inst = INSTRUMENTS[self.symbol]
        price = self.broker.price(self.symbol)
        if price is None or not math.isfinite(price) or price <= 0:
            logger.warning("overnight %s: no usable price; will retry", row.trade_date)
            return
        fx = self.broker.fx_rate(inst.currency, settings.base_currency)
        price_base = price * fx
        nav = self.broker.nav()
        shares = overnight.shares_for_sleeve(
            self.spy_weight * nav, price_base, settings.overnight_price_buffer
        )
        if shares < 1:
            self._finish(db, row, now, "STAY_CASH", note + " | SPY slice too small for one share")
            return

        entry, _ = overnight.order_plan(self.symbol, shares, self.broker.account())
        entry = dataclasses.replace(entry, transmit=True, ref=self._ref(row, "entry"))
        gate = check_orders([entry], nav, {self.symbol: price_base})
        row.decided_at, row.action, row.qty = now, "PLAN_BUY_CLOSE", shares
        if not gate.approved:
            row.entry_status, row.note = "rejected", f"{note} | risk gate: {gate.rejected[0][1]}"
            db.commit()
            notify(f"overnight {row.trade_date}: entry rejected ({gate.rejected[0][1]})")
            return

        # Persist intent BEFORE sending: if we crash mid-call the status stays 'submitting' and
        # the order is never placed a second time.
        row.entry_status, row.note = "submitting", note
        db.commit()
        try:
            fills = self.broker.place([entry])
        except Exception:
            logger.exception("overnight %s: entry placement outcome UNKNOWN", row.trade_date)
            row.note = f"{note} | placement outcome unknown: check IBKR, do not resubmit"
            db.commit()
            notify(f"overnight {row.trade_date}: entry outcome unknown, check IBKR")
            return
        row.entry_status = "submitted"
        db.commit()
        self._record_orders(db, [entry], fills)
        notify(f"overnight {row.trade_date}: BUY {shares} {self.symbol} MOC submitted")

    # ------------------------------------------------------------------ fills and exit

    def _advance(self, db: DbSession, row: OvernightDay, now: datetime) -> None:
        # Confirm the entry from the broker's executions, not from our own bookkeeping.
        filled = self.broker.filled_qty(self._ref(row, "entry"))
        if filled != row.entry_filled:
            row.entry_filled = filled
            row.entry_status = "filled" if row.qty and filled >= row.qty else "submitted"
            db.commit()

        market_open = self.broker.is_market_open(self.symbol)

        if row.entry_filled == 0:
            if now > _aware(row.close_at) + ENTRY_CONFIRM_GRACE and not market_open:
                row.entry_status = "unfilled"
                row.note = (row.note or "") + " | MOC entry never filled"
                db.commit()
                notify(f"overnight {row.trade_date}: entry never filled")
            return

        held = row.entry_filled - row.exit_filled
        if row.exit_status == "none":
            # Only for confirmed owned shares, and never before the close.
            if now >= _aware(row.close_at):
                self._place_exit(db, row, held, at_open=not market_open)
            return

        row.exit_filled = self.broker.filled_qty(self._ref(row, "exit")) + self.broker.filled_qty(
            self._ref(row, "late")
        )
        if row.exit_filled >= row.entry_filled:
            row.exit_status = "filled"
            db.commit()
            notify(f"overnight {row.trade_date}: exit complete")
            return
        db.commit()

        session = self.broker.session_today(self.symbol, now)
        if (
            row.exit_status == "submitted"
            and market_open
            and session is not None
            and now >= session.start + EXIT_ESCALATE_AFTER_OPEN
        ):
            self._place_exit(db, row, row.entry_filled - row.exit_filled, at_open=False, late=True)

    def _place_exit(
        self, db: DbSession, row: OvernightDay, shares: float, at_open: bool, late: bool = False
    ) -> None:
        quantity = int(shares)
        if quantity < 1:
            return
        ref = self._ref(row, "late" if late else "exit")
        order = Order(
            self.symbol,
            -float(quantity),
            "MKT",
            tif="OPG" if at_open else "DAY",
            account=self.broker.account(),
            ref=ref,
        )
        row.exit_status = "escalated" if late else "submitting"
        db.commit()
        try:
            fills = self.broker.place([order])
        except Exception:
            logger.exception("overnight %s: exit placement outcome UNKNOWN", row.trade_date)
            row.note = (row.note or "") + " | exit outcome unknown: check IBKR, do not resubmit"
            db.commit()
            notify(f"overnight {row.trade_date}: EXIT outcome unknown, check IBKR now")
            return
        row.exit_status = "escalated" if late else "submitted"
        db.commit()
        self._record_orders(db, [order], fills)
        kind = "market (late)" if late else ("OPG" if at_open else "market")
        notify(f"overnight {row.trade_date}: SELL {quantity} {self.symbol} {kind} submitted")

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _ref(row: OvernightDay, leg: str) -> str:
        return f"overnight:{row.trade_date.isoformat()}:{leg}"

    @staticmethod
    def _finish(db: DbSession, row: OvernightDay, now: datetime, action: str, note: str) -> None:
        row.decided_at, row.action, row.note = now, action, note
        db.commit()

    @staticmethod
    def _record_orders(db: DbSession, orders: list[Order], fills: list) -> None:
        try:
            record_orders_and_fills(db, orders, fills)
        except Exception:
            logger.exception("overnight: could not record orders (they were already sent)")


def plan_now(
    broker: OvernightBroker,
    bars_fn: BarsFn,
    intraday_fn: IntradayFn,
    config: overnight.OvernightConfig,
    spy_weight: float,
) -> dict:
    """What the rule would do with the latest session's 15:00 volatility, sized with the live
    price, FX and NAV. Sends nothing. (Outside market hours this replays the last full session.)"""
    intraday = intraday_fn()
    intraday = intraday.assign(ts=pd.to_datetime(intraday["ts"], utc=True))
    step = timedelta(minutes=overnight.BAR_MINUTES)
    last_day = intraday["ts"].dt.tz_convert("America/New_York").dt.date.max()
    day = intraday[intraday["ts"].dt.tz_convert("America/New_York").dt.date == last_day]
    opened, closed = day["ts"].min().to_pydatetime(), (day["ts"].max() + step).to_pydatetime()
    decision_at = overnight.decision_time(closed)
    iv = overnight.intraday_variance(day, opened, closed, decision_at)
    signal = overnight.next_signal(bars_fn(), config, iv)
    inst = INSTRUMENTS[SYMBOL]
    price = broker.price(SYMBOL)
    fx = broker.fx_rate(inst.currency, settings.base_currency)
    price_base = (price or float("nan")) * fx
    nav = broker.nav()
    shares = overnight.shares_for_sleeve(spy_weight * nav, price_base, settings.overnight_price_buffer)
    return {
        **signal,
        "session_replayed": str(last_day),
        "decision_at_utc": decision_at.isoformat(),
        "intraday_var_scaled": iv,
        f"price_{inst.currency}": price,
        f"fx_{inst.currency}_{settings.base_currency}": fx,
        f"price_{settings.base_currency}": price_base,
        "nav": nav,
        "spy_slice_weight": spy_weight,
        "spy_slice_value": spy_weight * nav,
        "min_weight": config.min_weight,
        "shares": shares if signal["action"] == "PLAN_BUY_CLOSE" else 0,
        "note": "plan only: nothing was sent",
    }


def main(once: bool = False, plan_only: bool = False) -> None:
    logging.basicConfig(level=logging.INFO)
    broker = IBKRBroker(client_id=settings.ib_client_id + 10)
    broker.connect()
    broker.check_setup([SYMBOL])  # account type/currency and contract resolution, fail fast
    config = default_config()
    bars_fn, intraday_fn = ibkr_bars(broker), ibkr_intraday(broker)
    spy_weight = blended_weights()[SYMBOL]

    if plan_only:
        import json

        plan = plan_now(broker, bars_fn, intraday_fn, config, spy_weight)
        print(json.dumps(plan, indent=2, allow_nan=False, default=str))
        broker.disconnect()
        return

    trader = OvernightTrader(
        broker, sessionmaker(create_engine(settings.database_url)), bars_fn, intraday_fn, config, spy_weight=spy_weight
    )
    while True:
        try:
            trader.tick(datetime.now(UTC))
        except Exception:
            logger.exception("overnight tick failed")
            notify("tradebot overnight: tick failed, see logs")
        if once:
            return
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="tradebot overnight strategy")
    parser.add_argument("--once", action="store_true", help="run a single scheduling step and exit")
    parser.add_argument("--plan-now", action="store_true", help="print what the model would do now; sends nothing")
    args = parser.parse_args()
    main(once=args.once, plan_only=args.plan_now)
