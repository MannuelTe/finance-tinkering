"""Pre-announcement screen for possible insider dealing (MAR Art. 8/14).

For each announcement, fit a market model on an estimation window, then measure abnormal return
and abnormal volume in a window just before the announcement. A high score is a reason to look,
not evidence of abuse: leaks, rumours and sector news produce the same pattern.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

MIN_ESTIMATION_OBSERVATIONS = 60
STOCK_COLUMNS = frozenset({"ret", "volume"})


@dataclass(frozen=True, slots=True)
class EventResult:
    event_date: pd.Timestamp
    n_est: int
    alpha: float
    beta: float
    car: float  # cumulative abnormal return over the event window
    car_t: float  # CAR / (residual sd * sqrt(window length))
    volume_z: float  # mean log-volume in window vs estimation window, in estimation sd
    flagged: bool

    def to_dict(self) -> dict[str, object]:
        """Return a serialization-friendly representation of the result."""
        return asdict(self)


def _validate_window(name: str, window: tuple[int, int]) -> None:
    start, end = window
    if start > end:
        raise ValueError(f"{name} start must not be after its end")
    if end >= 0:
        raise ValueError(f"{name} must end before the event date")


def pre_event_screen(
    stock: pd.DataFrame,
    market_ret: pd.Series,
    event_date: str | pd.Timestamp,
    est_window: tuple[int, int] = (-250, -30),
    event_window: tuple[int, int] = (-10, -1),
    car_t_min: float = 3.0,
    volume_z_min: float = 2.0,
) -> EventResult | None:
    """Evaluate one event against a market-model and abnormal-volume screen.

    ``stock`` must have a unique, increasing ``DatetimeIndex`` and ``ret`` and ``volume``
    columns. Windows are inclusive trading-day offsets relative to the first observation on or
    after ``event_date``. ``None`` means the observation cannot be scored with the requested
    windows or minimum data quality.
    """
    missing = STOCK_COLUMNS.difference(stock.columns)
    if missing:
        raise ValueError(f"stock is missing required columns: {', '.join(sorted(missing))}")
    if not isinstance(stock.index, pd.DatetimeIndex):
        raise TypeError("stock must use a DatetimeIndex")
    if not stock.index.is_monotonic_increasing or not stock.index.is_unique:
        raise ValueError("stock index must be unique and sorted in increasing order")
    if not isinstance(market_ret.index, pd.DatetimeIndex):
        raise TypeError("market_ret must use a DatetimeIndex")
    if not market_ret.index.is_monotonic_increasing or not market_ret.index.is_unique:
        raise ValueError("market_ret index must be unique and sorted in increasing order")
    _validate_window("est_window", est_window)
    _validate_window("event_window", event_window)
    if est_window[1] >= event_window[0]:
        raise ValueError("est_window must end before event_window starts")
    if car_t_min <= 0 or volume_z_min <= 0:
        raise ValueError("screen thresholds must be positive")

    event_date = pd.Timestamp(event_date)
    idx = stock.index
    pos = idx.searchsorted(event_date)
    if pos >= len(idx):
        return None
    e0, e1 = pos + est_window[0], pos + est_window[1]
    w0, w1 = pos + event_window[0], pos + event_window[1]
    if e0 < 0 or w0 < 0 or e1 >= len(stock) or w1 >= len(stock):
        return None

    est = stock.iloc[e0 : e1 + 1]
    win = stock.iloc[w0 : w1 + 1]
    mkt_est = market_ret.reindex(est.index)
    mkt_win = market_ret.reindex(win.index)
    ok = est["ret"].notna() & mkt_est.notna()
    volume_ok = est["volume"].notna()
    if (
        ok.sum() < MIN_ESTIMATION_OBSERVATIONS
        or volume_ok.sum() < MIN_ESTIMATION_OBSERVATIONS
        or mkt_win.isna().any()
        or win[["ret", "volume"]].isna().any().any()
    ):
        return None

    if float(mkt_est[ok].std(ddof=1)) == 0:
        return None
    beta, alpha = np.polyfit(mkt_est[ok], est["ret"][ok], 1)
    resid_sd = float(np.std(est["ret"][ok] - (alpha + beta * mkt_est[ok]), ddof=2))
    if not np.isfinite(resid_sd) or resid_sd <= 0:
        return None
    ar = win["ret"] - (alpha + beta * mkt_win)
    car = float(ar.sum())
    car_t = car / (resid_sd * np.sqrt(len(win)))

    if (est.loc[volume_ok, "volume"] < 0).any() or (win["volume"] < 0).any():
        return None
    lv_est = np.log1p(est.loc[volume_ok, "volume"])
    lv_std = float(lv_est.std(ddof=1))
    if not np.isfinite(lv_std) or lv_std == 0:
        return None
    volume_z = float((np.log1p(win["volume"]).mean() - lv_est.mean()) / lv_std)

    return EventResult(
        event_date=event_date,
        n_est=int(ok.sum()),
        alpha=float(alpha),
        beta=float(beta),
        car=car,
        car_t=float(car_t),
        volume_z=volume_z,
        flagged=bool(car_t >= car_t_min and volume_z >= volume_z_min),
    )


def screen_events(
    events: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    market_ret: pd.Series,
    **kwargs,
) -> pd.DataFrame:
    """Screen an event table and return one row for every scorable event.

    ``events`` must contain ``ticker`` and ``event_date``. Tickers absent from ``prices`` and
    events with insufficient history are omitted.
    """
    required = {"ticker", "event_date"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"events is missing required columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, object]] = []
    for _, ev in events.iterrows():
        df = prices.get(ev["ticker"])
        res = (
            pre_event_screen(df, market_ret, ev["event_date"], **kwargs) if df is not None else None
        )
        if res is not None:
            rows.append({"ticker": ev["ticker"], **res.to_dict()})
    columns = ["ticker", *EventResult.__dataclass_fields__]
    return pd.DataFrame(rows, columns=columns)
