"""Startup reconciliation of broker positions against the DB.

PURPOSE: Startup reconciliation of broker positions against the DB.
INPUTS:  a Broker.
OUTPUTS: logs any drift between broker and stored positions.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tradebot.broker.base import Broker
from tradebot.config import settings
from tradebot.state.models import PositionRecord

logger = logging.getLogger(__name__)


def reconcile(broker: Broker) -> None:
    """Sync DB position records with what the broker actually reports. Runs on every startup
    so a bot restart (including the daily Gateway restart) never trades on stale local state.
    Broker is always the source of truth; the DB is overwritten to match, never the reverse.
    """
    if not broker.is_connected():
        logger.warning("broker not connected; skipping reconciliation")
        return

    engine = create_engine(settings.database_url)
    broker_positions = {p.symbol: p for p in broker.positions()}

    with Session(engine) as session:
        db_positions = {p.symbol: p for p in session.query(PositionRecord).all()}

        for symbol, pos in broker_positions.items():
            record = db_positions.get(symbol)
            if record is None:
                session.add(PositionRecord(symbol=symbol, qty=pos.qty, avg_price=pos.avg_price))
            elif record.qty != pos.qty or record.avg_price != pos.avg_price:
                logger.warning(
                    "position drift for %s: db=%s/%s broker=%s/%s — overwriting with broker truth",
                    symbol,
                    record.qty,
                    record.avg_price,
                    pos.qty,
                    pos.avg_price,
                )
                record.qty = pos.qty
                record.avg_price = pos.avg_price

        for symbol, record in db_positions.items():
            if symbol not in broker_positions and record.qty != 0:
                logger.warning("db shows %s but broker has no position; zeroing", symbol)
                record.qty = 0.0

        session.commit()
