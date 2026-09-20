"""SPY overnight research: signal model, backtest, next-session plan, spread screen.

Ported from the standalone `ibkr_overnight.py` (archived under ../archive/) with identical
numerics. Like the original it NEVER submits orders: `order_plan` returns plan-only `Order`s
(transmit=False) that brokers refuse to place. It is research and planning tooling, not an
unattended scheduler; the runner does not use it.

Bars: a frame indexed by date with `open` and `close`, one row EVERY trading session,
ascending. Use consistently split AND dividend adjusted open/close for total returns; never mix
an adjusted close with a raw open. IBKR TRADES bars are a PRICE-return dataset (splits adjusted,
dividends not), so they omit dividend income; adjusted prices cannot determine share quantities.

Model: local IID Gaussian MLE (denominator n), 60 observations by default. Expected overnight
return comes from prior overnight returns. Both overnight and close-to-close daily volatility
are estimated and the larger variance is a conservative sizing denominator (NOT a fitted
overnight volatility). Entry requires mean - roundtrip cost > z * standard error of the mean;
the default z=0 is an EV filter, not evidence of significance. Sizing is
clip(fraction * net_mean / risk_variance, 0, cap) with no borrowed cash. Realized returns enter
later rolling windows, never their own signal.

Timing: row t is a sale at open t after buying close t-1. Its overnight estimate uses data
through open t-1; its daily estimate uses closes through t-2, both available BEFORE submitting
MOC on t-1. `next_signal` assumes every supplied bar is a completed session and makes a
conservative NEXT-session-close plan.

Costs: `cost_bps` is the ALL-IN roundtrip cost per invested dollar, not per side. Costs exclude
tax; no cash interest, dividend payment delay, commission minimums, volume impact, margin or
borrow costs are simulated. The backtest uses fractional theoretical exposure, not whole shares.

Production use would still need an exchange calendar (early closes, holidays), MOC cutoff
checks, current-price sizing with a price buffer and cash reserve, account/position/order
reconciliation, persistent idempotency, fill handling, disconnect recovery, corporate actions,
alerts and an emergency exit policy. Overnight gap losses remain possible.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from tradebot.broker.base import Order

TRADING_DAYS = 252
_BPS = 10_000


@dataclass(frozen=True)
class OvernightConfig:
    window: int = 60
    cost_bps: float = 2.0
    fraction: float = 0.25
    cap: float = 1.0
    z: float = 0.0
    # binary: each day is either a full-size trade (weight = cap) or no trade, instead of a
    # fractional size that scales with the model's confidence. The entry test is unchanged.
    binary: bool = False
    # Binary mode trades the whole position only if the model's sized weight (with today's
    # volatility in the risk term) is at least this; below it the day is skipped. 0 keeps the
    # earlier rule: trade whenever the expected net return is positive.
    min_weight: float = 0.0

    def __post_init__(self) -> None:
        if self.window < 3 or not all(
            math.isfinite(x) for x in (self.cost_bps, self.fraction, self.cap, self.z)
        ):
            raise ValueError("Invalid configuration")
        if self.cost_bps < 0 or not 0 < self.fraction <= 1 or not 0 < self.cap <= 1 or self.z < 0:
            raise ValueError("Costs/z must be nonnegative; fraction/cap in (0,1]")
        if not 0 <= self.min_weight <= self.cap or not math.isfinite(self.min_weight):
            raise ValueError("min_weight must be in [0, cap]")


# --------------------------------------------------------------------------- data


def validate_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Return a clean `open`/`close` float frame or raise. Dates must be unique and ascending."""
    index = bars.index
    if index.has_duplicates or not index.is_monotonic_increasing or index.hasnans:
        raise ValueError("Dates must be unique, valid and ascending")
    prices = bars[["open", "close"]].astype(float)
    if not np.isfinite(prices).all().all() or (prices <= 0).any().any():
        raise ValueError("Prices must be finite and positive")
    return prices


def load_bars(path: str) -> pd.DataFrame:
    """CSV with columns date,open,close."""
    return validate_bars(pd.read_csv(path, parse_dates=["date"]).set_index("date"))


def frame_to_bars(frame: pd.DataFrame) -> pd.DataFrame:
    """Engine bar frame (ts, open, ..., close) -> date-indexed open/close bars."""
    dates = pd.DatetimeIndex(pd.to_datetime(frame["ts"]))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    bars = pd.DataFrame(
        {"open": frame["open"].to_numpy(), "close": frame["close"].to_numpy()},
        index=pd.DatetimeIndex(dates.normalize(), name="date"),
    )
    return validate_bars(bars)


# --------------------------------------------------------------------------- model


def estimate(
    overnight, daily, c: OvernightConfig, intraday_var: float | None = None
) -> dict[str, float | None]:
    """Expected overnight return and position weight.

    `intraday_var` (optional) is today's realized variance up to the decision time, scaled to a
    full session. It joins the overnight and daily variances in the risk term (the largest wins,
    a conservative sizing denominator), so a stormy day lowers the sized weight.
    """
    a, b = np.asarray(overnight)[-c.window :], np.asarray(daily)[-c.window :]
    if len(a) < c.window or len(b) < c.window or not np.isfinite(np.r_[a, b]).all():
        return {
            "mu": np.nan, "sigma_overnight": np.nan, "sigma_daily": np.nan,
            "sigma_intraday": None, "risk_sigma": np.nan, "raw_weight": 0.0, "weight": 0.0,
        }  # fmt: skip
    mu, so, sd = float(a.mean()), float(a.std(ddof=0)), float(b.std(ddof=0))
    net = mu - c.cost_bps / _BPS
    iv = float(intraday_var) if intraday_var is not None and math.isfinite(intraday_var) else None
    v = max(so**2, sd**2, iv if iv is not None else 0.0)
    if v < 1e-12 or net <= c.z * so / math.sqrt(c.window):
        raw = 0.0
    else:
        raw = min(c.cap, c.fraction * net / v)
    weight = raw
    if c.binary:
        weight = c.cap if raw > 0 and raw >= c.min_weight else 0.0
    return {
        "mu": mu,
        "sigma_overnight": so,
        "sigma_daily": sd,
        "sigma_intraday": math.sqrt(iv) if iv is not None else None,
        "risk_sigma": math.sqrt(v),
        "raw_weight": raw,
        "weight": weight,
    }


def backtest(
    d: pd.DataFrame,
    c: OvernightConfig,
    initial: float = 10_000,
    intraday: pd.Series | None = None,
) -> pd.DataFrame:
    """`intraday`: optional Series (index = decision date, value = scaled intraday variance up to
    the decision time). When given, a decision day without a value is skipped (no trade), never
    traded blind."""
    if initial <= 0 or not math.isfinite(initial):
        raise ValueError("Initial equity must be positive")
    if len(d) < c.window + 3:
        raise ValueError("Insufficient history after conservative signal lag")
    overnight = d.open / d.close.shift(1) - 1
    daily = d.close.pct_change(fill_method=None)
    cost = c.cost_bps / _BPS
    rows = []
    for t in range(c.window + 2, len(d)):
        iv = None
        if intraday is not None:
            iv = intraday.get(d.index[t - 1])
            iv = None if iv is None or not math.isfinite(iv) else float(iv)
        e = estimate(overnight.iloc[:t], daily.iloc[: t - 1], c, iv)
        missing = intraday is not None and iv is None
        if missing:
            e = {**e, "raw_weight": 0.0, "weight": 0.0}
        r = float(overnight.iloc[t])
        rows.append(
            dict(
                date=d.index[t],
                decision_date=d.index[t - 1],
                intraday_missing=missing,
                **e,
                overnight_return=r,
                strategy_return=e["weight"] * (r - cost),
                overnight_net=r - cost,
                buy_hold=float(daily.iloc[t]),
            )
        )
    out = pd.DataFrame(rows).set_index("date")
    for name in ["strategy_return", "overnight_net", "buy_hold"]:
        if (out[name] <= -1).any():
            raise ValueError("Insolvent path; inspect data/costs")
        out[name + "_equity"] = initial * (1 + out[name]).cumprod()
    return out


def summary(out: pd.DataFrame, initial: float) -> dict:
    result: dict = {}
    for name in ["strategy_return", "overnight_net", "buy_hold"]:
        r = out[name]
        eq = np.r_[initial, out[name + "_equity"].to_numpy()]
        result[name] = {
            "ending_equity": float(eq[-1]),
            "annualized_252": float((eq[-1] / initial) ** (TRADING_DAYS / len(r)) - 1),
            "annualized_vol": float(r.std(ddof=0) * np.sqrt(TRADING_DAYS)),
            "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min()),
        }
    result["sessions"] = len(out)
    result["traded_sessions"] = int((out.weight > 0).sum())
    result["note"] = (
        "Common evaluation dates; buy_hold excludes entry/exit costs. No tax/cash interest."
    )
    return result


def next_signal(d: pd.DataFrame, c: OvernightConfig, intraday_var: float | None = None) -> dict:
    """Conservative plan for the NEXT session's close. Every supplied bar must be completed."""
    overnight = (d.open / d.close.shift(1) - 1).dropna()
    daily = d.close.pct_change(fill_method=None).dropna()
    e = estimate(overnight, daily, c, intraday_var)
    if not math.isfinite(e["mu"]):
        raise ValueError("Insufficient history")
    return dict(
        **e,
        history_through=str(d.index[-1].date()),
        action="PLAN_BUY_CLOSE" if e["weight"] > 0 else "STAY_CASH",
        transmit=False,
        scope="Conservative next-session-close plan only",
    )


# --------------------------------------------------------------------------- order plan

PLAN_REF = "overnight_mle_REQUIRES_SUPERVISOR"


def order_plan(symbol: str, quantity: int, account: str) -> tuple[Order, Order]:
    """Plan-only entry (BUY MOC) and exit (SELL MKT at the opening auction). Neither is
    transmittable: brokers refuse transmit=False orders. Submit the exit ONLY for confirmed,
    owned, filled shares before the next session's opening cutoff, never alongside the entry."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0 or not account:
        raise ValueError("Positive integer quantity and explicit account required")
    entry = Order(
        symbol, float(quantity), "MOC", tif="DAY", transmit=False, account=account, ref=PLAN_REF
    )
    exit_order = Order(
        symbol, -float(quantity), "MKT", tif="OPG", transmit=False, account=account, ref=PLAN_REF
    )
    return entry, exit_order


# --------------------------------------------------------------------------- spread screen


def screen_frames(
    returns: pd.DataFrame,
    quotes: pd.DataFrame,
    min_beta: float = 1.1,
    min_corr: float = 0.8,
    min_saving: float = 0.1,
) -> list[dict]:
    """Does any candidate ETF offer SPY-like overnight exposure at a cheaper spread?

    returns: date,symbol,return -- aligned close->next-open simple returns, every symbol on the
    SAME cash-market session endpoints (futures included).
    quotes: date,slot,symbol,bid,ask -- one synchronized valid NBBO per slot per symbol,
    sampled at a fixed cadence in chosen entry/exit windows. Use exchange timestamps and reject
    stale or delayed quotes upstream.

    At least 60 paired return observations and 30 paired quote days are required. Per-day paired
    mean full spreads; moving-block bootstrap by days, 5-day blocks. A candidate must meet
    beta >= min_beta, correlation >= min_corr and a RAW saving whose lower CI exceeds
    min_saving bps; beta-normalized savings alone do not qualify. The CI is exploratory, not
    multiple-testing corrected. Do not optimise a strategy with full-sample screening.
    """
    r = returns.pivot(index="date", columns="symbol", values="return").sort_index()
    q = quotes.copy()
    if "SPY" not in r or "SPY" not in set(q.symbol):
        raise ValueError("SPY is required in both datasets")
    if q.duplicated(["date", "slot", "symbol"]).any():
        raise ValueError("Duplicate quote slots")
    if not np.isfinite(q[["bid", "ask"]]).all().all() or (q.bid <= 0).any() or (q.ask <= q.bid).any():
        raise ValueError("Reject invalid, locked or crossed quotes")
    q["bps"] = _BPS * (q.ask - q.bid) / ((q.ask + q.bid) / 2)
    p = q.pivot(index=["date", "slot"], columns="symbol", values="bps").sort_index()

    results = []
    for symbol in sorted((set(r.columns) & set(p.columns)) - {"SPY"}):
        rr = r[["SPY", symbol]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(rr) < 60 or rr.SPY.var(ddof=0) <= 0:
            continue
        beta = float(np.cov(rr[symbol], rr.SPY, ddof=0)[0, 1] / rr.SPY.var(ddof=0))
        corr = float(rr.corr().iloc[0, 1])
        pairs = p[["SPY", symbol]].dropna()
        daily = pairs.groupby(level="date").mean()
        if len(daily) < 30 or beta <= 0 or not math.isfinite(corr):
            continue
        delta = (daily.SPY - daily[symbol]).to_numpy()
        # Circular moving-block resampling preserves short-run serial dependence.
        rng = np.random.default_rng(42)
        n, block = len(delta), 5
        starts = rng.integers(0, n, size=(3000, math.ceil(n / block)))
        idx = ((starts[..., None] + np.arange(block)) % n).reshape(3000, -1)[:, :n]
        low, high = np.quantile(delta[idx].mean(axis=1), [0.025, 0.975])
        results.append(
            {
                "symbol": symbol,
                "overnight_beta": beta,
                "correlation": corr,
                "paired_return_days": len(rr),
                "paired_quote_days": n,
                "spy_mean_spread_bps": float(daily.SPY.mean()),
                "candidate_mean_spread_bps": float(daily[symbol].mean()),
                "raw_saving_bps": float(delta.mean()),
                "ci95_low_bps": float(low),
                "ci95_high_bps": float(high),
                "beta_normalized_saving_bps": float((daily.SPY - daily[symbol] / beta).mean()),
                "qualifies": bool(beta >= min_beta and corr >= min_corr and low > min_saving),
            }
        )
    return results


def screen(returns_path: str, quotes_path: str, **kwargs: float) -> list[dict]:
    return screen_frames(pd.read_csv(returns_path), pd.read_csv(quotes_path), **kwargs)


# --------------------------------------------------------------------------- daily schedule

# The decision moment is drawn uniformly from [close - 60 min, close - 15 min]: 15:00-15:45 ET on
# a normal day, and it moves with early closes. Closing-auction (MOC) orders are cut off 10
# minutes before the close, so a draw can never land after the cutoff.
DECISION_OPENS_BEFORE_CLOSE = timedelta(minutes=60)
DECISION_CLOSES_BEFORE_CLOSE = timedelta(minutes=15)
MOC_CUTOFF_BEFORE_CLOSE = timedelta(minutes=10)


def decision_window(close: datetime) -> tuple[datetime, datetime]:
    return close - DECISION_OPENS_BEFORE_CLOSE, close - DECISION_CLOSES_BEFORE_CLOSE


def draw_decision_time(close: datetime, rng: random.Random | None = None) -> datetime:
    """Uniform random instant (whole seconds) inside the decision window."""
    start, end = decision_window(close)
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=(rng or random.SystemRandom()).randint(0, span))


def shares_for_sleeve(sleeve: float, price_base: float, buffer: float = 0.01) -> int:
    """Whole shares affordable within `sleeve`. A MOC price is unknown when sizing, so the
    price is inflated by `buffer` to keep the auction fill inside the sleeve."""
    if not (math.isfinite(sleeve) and math.isfinite(price_base)) or sleeve <= 0 or price_base <= 0:
        return 0
    if not 0 <= buffer < 1:
        raise ValueError("buffer must be in [0, 1)")
    return math.floor(sleeve / (price_base * (1 + buffer)))


def decision_time(close: datetime) -> datetime:
    """The daily decision instant: 60 minutes before the close, i.e. 15:00 ET on a normal day
    and 12:00 ET on a 13:00 early close."""
    return close - DECISION_OPENS_BEFORE_CLOSE


# --------------------------------------------------------------------------- intraday volatility

BAR_MINUTES = 5


def intraday_variance(
    bars: pd.DataFrame,
    session_open: datetime,
    session_close: datetime,
    decision_at: datetime,
    bar_minutes: int = BAR_MINUTES,
    min_coverage: float = 0.9,
) -> float | None:
    """Realized variance from the open up to `decision_at`, scaled to a full session.

    `bars`: columns ts (timezone-aware bar START), open, close. Only bars that had COMPLETED by
    the decision instant are used. Variance is the sum of squared log returns (first return
    measured from the session's opening price), multiplied by session length / elapsed length so
    it is comparable to a daily variance. Returns None when too few bars exist (coverage below
    `min_coverage`) or prices are unusable: the caller must then skip the day, never guess.
    """
    step = timedelta(minutes=bar_minutes)
    day = bars[(bars["ts"] >= session_open) & (bars["ts"] + step <= decision_at)].sort_values("ts")
    expected = int((decision_at - session_open) / step)
    if expected <= 0 or len(day) < min_coverage * expected:
        return None
    opens, closes = day["open"].to_numpy(float), day["close"].to_numpy(float)
    if not (np.isfinite(opens).all() and np.isfinite(closes).all()) or (closes <= 0).any() or opens[0] <= 0:
        return None
    returns = np.log(closes / np.r_[opens[0], closes[:-1]])
    elapsed = (day["ts"].iloc[-1] + step - session_open).total_seconds()
    total = (session_close - session_open).total_seconds()
    return float(np.sum(returns**2) * total / elapsed)


def intraday_variance_by_day(
    bars: pd.DataFrame, time_zone: str = "America/New_York", bar_minutes: int = BAR_MINUTES
) -> pd.DataFrame:
    """Per trading date: the scaled intraday variance at that day's own decision time.

    Sessions are inferred from the bars (first bar start, last bar end), so early closes get an
    earlier decision time automatically. Days that do not start at 09:30 local, or lack enough
    bars, are omitted (the backtest then skips them).
    """
    tz = ZoneInfo(time_zone)
    step = timedelta(minutes=bar_minutes)
    frame = bars.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["date"] = frame["ts"].dt.tz_convert(tz).dt.normalize().dt.tz_localize(None)
    rows = []
    for date, day in frame.groupby("date"):
        first, last = day["ts"].min(), day["ts"].max() + step
        if first.tz_convert(tz).strftime("%H:%M") != "09:30":
            continue
        decision_at = decision_time(last.to_pydatetime())
        var = intraday_variance(day, first.to_pydatetime(), last.to_pydatetime(), decision_at, bar_minutes)
        if var is not None:
            rows.append({"date": date, "intraday_var": var, "session_close_utc": last, "decision_at_utc": decision_at})
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(
        columns=["intraday_var", "session_close_utc", "decision_at_utc"]
    )
