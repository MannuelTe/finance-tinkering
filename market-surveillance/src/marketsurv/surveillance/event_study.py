"""Pre-announcement screen for possible insider dealing (MAR Art. 8/14).

For each announcement, fit a market model on an estimation window, then measure abnormal return
and abnormal volume in a window just before the announcement. A high score is a reason to look,
not evidence of abuse: leaks, rumours and sector news produce the same pattern.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class EventResult:
    event_date: pd.Timestamp
    n_est: int
    alpha: float
    beta: float
    car: float  # cumulative abnormal return over the event window
    car_t: float  # CAR / (residual sd * sqrt(window length))
    volume_z: float  # mean log-volume in window vs estimation window, in estimation sd
    flagged: bool


def pre_event_screen(
    stock: pd.DataFrame,
    market_ret: pd.Series,
    event_date: str | pd.Timestamp,
    est_window: tuple[int, int] = (-250, -30),
    event_window: tuple[int, int] = (-10, -1),
    car_t_min: float = 3.0,
    volume_z_min: float = 2.0,
) -> EventResult | None:
    """stock: DataFrame indexed by date with columns `ret` and `volume`.

    Windows are trading-day offsets relative to event_date (0 = announcement day). Returns None
    if the history is too short.
    """
    event_date = pd.Timestamp(event_date)
    idx = stock.index
    pos = idx.searchsorted(event_date)
    if pos >= len(idx):
        return None
    e0, e1 = pos + est_window[0], pos + est_window[1]
    w0, w1 = pos + event_window[0], pos + event_window[1]
    if e0 < 0 or e1 - e0 < 60:
        return None

    est = stock.iloc[e0 : e1 + 1]
    win = stock.iloc[w0 : w1 + 1]
    mkt_est = market_ret.reindex(est.index)
    mkt_win = market_ret.reindex(win.index)
    ok = est["ret"].notna() & mkt_est.notna()
    if ok.sum() < 60 or mkt_win.isna().any() or win["ret"].isna().any():
        return None

    beta, alpha = np.polyfit(mkt_est[ok], est["ret"][ok], 1)
    resid_sd = float(np.std(est["ret"][ok] - (alpha + beta * mkt_est[ok]), ddof=2))
    if resid_sd == 0:  # flat price history: nothing to standardise against
        return None
    ar = win["ret"] - (alpha + beta * mkt_win)
    car = float(ar.sum())
    car_t = car / (resid_sd * np.sqrt(len(win)))

    lv_est = np.log1p(est["volume"])
    volume_z = float((np.log1p(win["volume"]).mean() - lv_est.mean()) / lv_est.std(ddof=1))

    return EventResult(
        event_date=event_date, n_est=int(ok.sum()), alpha=float(alpha), beta=float(beta),
        car=car, car_t=float(car_t), volume_z=volume_z,
        flagged=bool(car_t >= car_t_min and volume_z >= volume_z_min),
    )


def screen_events(
    events: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    market_ret: pd.Series,
    **kwargs,
) -> pd.DataFrame:
    """events: columns ticker, event_date. prices: ticker -> DataFrame(ret, volume)."""
    rows = []
    for _, ev in events.iterrows():
        df = prices.get(ev["ticker"])
        res = pre_event_screen(df, market_ret, ev["event_date"], **kwargs) if df is not None else None
        if res is not None:
            rows.append({"ticker": ev["ticker"], **res.__dict__})
    return pd.DataFrame(rows)
