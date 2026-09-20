from __future__ import annotations

import logging
import math
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ib_async import IB, Forex, MarketOrder, Stock
from ib_async import Order as IBOrder

from tradebot.broker.base import Bar, Fill, Order, Position, Session
from tradebot.config import settings
from tradebot.data.sources.yfinance import fx_rate as yahoo_fx_rate
from tradebot.instruments import INSTRUMENTS

logger = logging.getLogger(__name__)


def contract_for(symbol: str) -> Stock:
    """Build the IBKR contract for a registered instrument (exchange, currency and primary
    exchange come from the registry, never from the symbol string)."""
    try:
        inst = INSTRUMENTS[symbol]
    except KeyError:
        raise KeyError(f"{symbol!r} is not in tradebot.instruments.INSTRUMENTS") from None
    return Stock(
        inst.symbol, inst.exchange, inst.currency, primaryExchange=inst.primary_exchange or ""
    )


def to_ib_order(order: Order) -> IBOrder:
    """Translate an engine Order into an IBKR order, or raise. Unknown types and impossible
    combinations fail loudly instead of silently turning into a market order."""
    if not order.transmit:
        raise ValueError(f"{order.symbol}: plan-only order (transmit=False) must not be placed")
    if order.qty == 0 or not math.isfinite(order.qty):
        raise ValueError(f"{order.symbol}: invalid quantity {order.qty}")
    action, quantity = ("BUY" if order.qty > 0 else "SELL"), abs(order.qty)

    if order.order_type == "MKT":
        ib_order: IBOrder = MarketOrder(action, quantity)
    elif order.order_type == "MOC":
        ib_order = IBOrder(action=action, totalQuantity=quantity, orderType="MOC")
    elif order.order_type == "LMT":
        if order.limit_price is None or not math.isfinite(order.limit_price) or order.limit_price <= 0:
            raise ValueError(f"{order.symbol}: LMT order needs a positive limit_price")
        ib_order = IBOrder(
            action=action, totalQuantity=quantity, orderType="LMT", lmtPrice=order.limit_price
        )
    else:
        raise ValueError(f"{order.symbol}: unsupported order type {order.order_type!r}")

    ib_order.tif = order.tif
    ib_order.outsideRth = False
    if order.account:
        ib_order.account = order.account
    if order.ref:
        ib_order.orderRef = order.ref
    return ib_order


def session_for_date(liquid_hours: str, time_zone: str, now: datetime) -> Session | None:
    """The regular session that starts on `now`'s date in the exchange's own time zone, or None
    on weekends and holidays. Early closes come through naturally: IBKR lists the real hours.
    The returned instants are in the exchange time zone (so `.local_date` is the trade date)."""
    try:
        tz = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError:
        return None
    today = now.astimezone(tz).date()
    for window in liquid_hours.split(";"):
        if "CLOSED" in window or "-" not in window:
            continue
        try:
            start_s, end_s = window.split("-")
            start = datetime.strptime(start_s, "%Y%m%d:%H%M").replace(tzinfo=tz)
            end = datetime.strptime(end_s, "%Y%m%d:%H%M").replace(tzinfo=tz)
        except ValueError:
            continue
        if start.date() == today:
            return Session(start, end)
    return None


def in_session(liquid_hours: str, time_zone: str, now: datetime) -> bool:
    """Whether `now` falls inside one of IBKR's regular-session windows.

    `liquid_hours` is IBKR's ContractDetails.liquidHours, e.g.
    "20260918:0930-20260918:1600;20260919:CLOSED;20260921:0930-20260921:1600", expressed in the
    exchange's own `time_zone`. Anything unparsable counts as closed."""
    try:
        tz = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError:
        logger.warning("unknown exchange time zone %r; treating the market as closed", time_zone)
        return False
    for window in liquid_hours.split(";"):
        if "CLOSED" in window or "-" not in window:
            continue
        try:
            start_s, end_s = window.split("-")
            start = datetime.strptime(start_s, "%Y%m%d:%H%M").replace(tzinfo=tz)
            end = datetime.strptime(end_s, "%Y%m%d:%H%M").replace(tzinfo=tz)
        except ValueError:
            continue
        if start <= now < end:
            return True
    return False


class IBKRBroker:
    """ib_async-backed broker talking to the IB Gateway container over IB_HOST:IB_PORT.

    NOTE: is_connected() reflects the socket to Gateway, not Gateway's own connection to
    IBKR servers. Gateway restarts daily (see docker-compose AUTO_RESTART_TIME) and may sit
    waiting on a 2FA push for minutes; callers must treat is_connected() == False as "do
    nothing this cycle", never as a signal to guess a position or retry aggressively.
    """

    def __init__(
        self, fx_fallback: Callable[[str, str], float] = yahoo_fx_rate, client_id: int | None = None
    ) -> None:
        self._ib = IB()
        self._client_id = client_id
        self._fx_fallback = fx_fallback
        self._hours: dict[str, tuple[str, str]] = {}  # symbol -> (liquidHours, timeZoneId)

    @property
    def ib(self) -> IB:
        return self._ib

    def connect(self) -> None:
        if not self._ib.isConnected():
            self._ib.connect(settings.ib_host, settings.ib_port, clientId=self._client_id or settings.ib_client_id)

    def disconnect(self) -> None:
        if self._ib.isConnected():
            self._ib.disconnect()

    def is_connected(self) -> bool:
        return self._ib.isConnected()

    def check_setup(self, symbols: Iterable[str]) -> None:
        """Startup safety check; raises RuntimeError with every problem found.

        - the account type matches IB_MODE (paper accounts are DU...);
        - the account is denominated in settings.base_currency (NAV and sizing assume it);
        - every symbol resolves to exactly one IBKR contract (catches wrong symbols/exchanges
          before a single order is sized).
        """
        problems: list[str] = []

        # Paper account ids start with "DU". Refuse a live account under IB_MODE=paper and vice
        # versa, so a credentials mix-up can never silently trade real money (or the reverse).
        for account in self._ib.managedAccounts():
            is_paper_account = account.startswith("DU")
            if settings.ib_mode == "paper" and not is_paper_account:
                problems.append(f"IB_MODE=paper but account {account[:2]}*** is not a paper account")
            if settings.ib_mode == "live" and is_paper_account:
                problems.append(f"IB_MODE=live but account {account[:2]}*** is a paper account")

        currencies = {
            row.currency
            for row in self._ib.accountSummary()
            if row.tag == "NetLiquidation" and row.currency
        }
        if currencies and currencies != {settings.base_currency}:
            problems.append(
                f"account NetLiquidation currency {sorted(currencies)} != "
                f"BASE_CURRENCY {settings.base_currency}"
            )

        for symbol in symbols:
            contract = contract_for(symbol)
            qualified = self._ib.qualifyContracts(contract)
            if not qualified or not contract.conId:
                problems.append(f"{symbol}: contract did not resolve ({contract})")
            else:
                logger.info(
                    "qualified %s -> conId=%s %s/%s", symbol, contract.conId,
                    contract.primaryExchange, contract.currency,
                )

        if problems:
            raise RuntimeError("IBKR setup check failed:\n  " + "\n  ".join(problems))

    def nav(self) -> float:
        for row in self._ib.accountSummary():
            if row.tag == "NetLiquidation":
                return float(row.value)
        return 0.0

    def positions(self) -> list[Position]:
        return [
            Position(symbol=p.contract.symbol, qty=p.position, avg_price=p.avgCost)
            for p in self._ib.positions()
        ]

    def place(self, orders: list[Order]) -> list[Fill]:
        # Translate the whole batch first: an invalid or plan-only order must fail before any
        # order in the batch has been sent, not halfway through.
        prepared = [(o, contract_for(o.symbol), to_ib_order(o)) for o in orders]
        fills: list[Fill] = []
        for order, contract, ib_order in prepared:
            trade = self._ib.placeOrder(contract, ib_order)
            self._ib.sleep(0)  # pump the event loop so the initial ack/fills land
            for f in trade.fills:
                fills.append(
                    Fill(symbol=order.symbol, qty=f.execution.shares, price=f.execution.price, ts=f.time)
                )
        return fills

    def bars(self, symbol: str, lookback_days: int) -> list[Bar]:
        contract = contract_for(symbol)
        raw = self._ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=f"{lookback_days} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
        )
        return [
            Bar(
                ts=b.date if isinstance(b.date, datetime) else datetime.combine(b.date, datetime.min.time()),
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
            )
            for b in raw
        ]

    def is_market_open(self, symbol: str) -> bool:
        details = self._ib.reqContractDetails(contract_for(symbol))
        if not details:
            logger.warning("no contract details for %s; treating its market as closed", symbol)
            return False
        d = details[0]
        return in_session(d.liquidHours, d.timeZoneId, datetime.now(UTC))

    def account(self) -> str:
        """The single managed account. Refuses to guess when there are several."""
        accounts = self._ib.managedAccounts()
        if len(accounts) != 1:
            raise RuntimeError(f"expected exactly one managed account, found {len(accounts)}")
        return accounts[0]

    def session_today(self, symbol: str, now: datetime) -> Session | None:
        details = self._ib.reqContractDetails(contract_for(symbol))
        if not details:
            return None
        return session_for_date(details[0].liquidHours, details[0].timeZoneId, now)

    def filled_qty(self, ref: str) -> float:
        """Shares filled so far for orders carrying `ref` (orderRef), from IBKR's executions.
        This is confirmation from the broker, not from our own bookkeeping."""
        return float(
            sum(
                f.execution.shares
                for f in self._ib.reqExecutions()
                if getattr(f.execution, "orderRef", "") == ref
            )
        )

    def open_order_symbols(self) -> set[str]:
        # reqAllOpenOrders (not openTrades) so orders from other API clients and from TWS/the
        # web portal count too. Active = PendingSubmit/ApiPending/PreSubmitted/Submitted, which
        # includes market orders queued while the exchange is closed.
        return {t.contract.symbol for t in self._ib.reqAllOpenOrders() if t.isActive()}

    def price(self, symbol: str) -> float | None:
        bars = self.bars(symbol, lookback_days=5)
        return bars[-1].close if bars else None

    def fx_rate(self, currency: str, base: str) -> float:
        """Units of `base` per 1 `currency`. IBKR first; if it has no FX data for us, Yahoo.

        IBKR refuses IDEALPRO quotes without a market-data subscription (error 10089/162, seen
        on the paper account), and the account's own ExchangeRate table only lists currencies it
        holds. The rate is only used to size orders and check the notional cap, where a small
        error is harmless: IBKR converts at its own rate when the order actually executes."""
        if currency == base:
            return 1.0
        try:
            return self._ib_fx_rate(currency, base)
        except ValueError:
            logger.warning(
                "no IBKR FX data for %s->%s (needs an IDEALPRO market-data subscription); "
                "using Yahoo", currency, base,
            )
            return self._fx_fallback(currency, base)

    def _ib_fx_rate(self, currency: str, base: str) -> float:
        """IDEALPRO only lists each pair in one direction (EURUSD, not USDEUR), so try
        currency+base first and fall back to the inverse pair."""
        for pair, invert in ((currency + base, False), (base + currency, True)):
            contract = Forex(pair)
            if not self._ib.qualifyContracts(contract):
                continue
            raw = self._ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr="5 D",
                barSizeSetting="1 day",
                whatToShow="MIDPOINT",
                useRTH=True,
            )
            if raw:
                rate = float(raw[-1].close)
                return 1.0 / rate if invert else rate
        raise ValueError(f"no IBKR FX rate available for {currency}->{base}")
