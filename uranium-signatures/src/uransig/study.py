"""Event study: abnormal returns around uranium news, signed so that 'up' means
'moved the way the news points', and a bootstrap test of bull/bear symmetry.

The signature of a group of events is its mean signed cumulative abnormal return
(CAR) path from day -PRE to day +POST. Speed is read off that path:

    pre-drift   CAR(-20,-1)    moved before the news was public
    jump        CAR(0,+1)      priced on the day and the next
    drift       CAR(+2,+20)    kept moving after
    speed       jump / CAR(0,+20)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

PRE, POST = 20, 60
EST = (-280, -30)  # market-model estimation window, trading days
MIN_EST = 120

WINDOWS = {"pre_drift": (-20, -1), "jump": (0, 1), "drift": (2, 20), "late": (21, 60)}


def load_events(path) -> pd.DataFrame:
    ev = pd.read_csv(path, parse_dates=["date"], keep_default_na=False)
    ev["sign"] = ev["direction"].map({"bull": 1.0, "bear": -1.0, "none": 1.0})
    return ev.sort_values("date").reset_index(drop=True)


def align(dates: pd.Series, index: pd.DatetimeIndex, session=None) -> np.ndarray:
    """Day 0: the first trading day on or after the news, or strictly after it when the
    news came out after the close."""
    pos = index.searchsorted(pd.DatetimeIndex(dates), side="left")
    if session is not None:
        on_day = index[np.minimum(pos, len(index) - 1)] == pd.DatetimeIndex(dates)
        pos = pos + ((np.asarray(session) == "post") & on_day)
    return pos


def abnormal_path(ret: pd.DataFrame, pos: int, names, market) -> pd.Series | None:
    """Equal-weight abnormal return of the available names, days -PRE..+POST.

    Each name gets its own market model (OLS on the market columns) over EST.
    """
    lo, hi = pos + EST[0], pos + EST[1]
    if lo < 0 or pos + POST >= len(ret):
        return None
    X_est = np.column_stack([np.ones(hi - lo), ret[list(market)].iloc[lo:hi].to_numpy()])
    win = slice(pos - PRE, pos + POST + 1)
    X_win = np.column_stack([np.ones(PRE + POST + 1), ret[list(market)].iloc[win].to_numpy()])
    ars = []
    for n in names:
        y = ret[n].iloc[lo:hi].to_numpy()
        ok = ~np.isnan(y) & ~np.isnan(X_est).any(axis=1)
        yw = ret[n].iloc[win].to_numpy()
        if ok.sum() < MIN_EST or np.isnan(yw).any():
            continue
        b, *_ = np.linalg.lstsq(X_est[ok], y[ok], rcond=None)
        ars.append(yw - X_win @ b)
    if not ars:
        return None
    return pd.Series(np.mean(ars, axis=0), index=range(-PRE, POST + 1))


def event_paths(ret, events, names, market) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Signed abnormal returns (rows = event, cols = day) and the events kept."""
    rows, kept = [], []
    for (_, e), pos in zip(events.iterrows(), align(events["date"], ret.index, events.get("session"))):
        ar = abnormal_path(ret, pos, names, market)
        if ar is None:
            continue
        rows.append(e["sign"] * ar)
        kept.append({**e.to_dict(), "day0": ret.index[pos].date()})
    return pd.DataFrame(rows).reset_index(drop=True), pd.DataFrame(kept)


def window_sums(ar: pd.DataFrame) -> pd.DataFrame:
    out = {k: ar.loc[:, a:b].sum(axis=1) for k, (a, b) in WINDOWS.items()}
    out["car_0_20"] = ar.loc[:, 0:20].sum(axis=1)
    return pd.DataFrame(out)


def signature(ar: pd.DataFrame) -> dict:
    w = window_sums(ar).mean()
    d = w.to_dict()
    d["speed"] = w["jump"] / w["car_0_20"] if w["car_0_20"] > 0 else np.nan
    d["n"] = len(ar)
    return d


@dataclass
class Symmetry:
    bull: dict
    bear: dict
    diff: dict      # bull minus bear
    ci: dict        # 90% bootstrap interval of the difference
    p: dict         # two-sided bootstrap p-value of the difference


def symmetry_test(bull: pd.DataFrame, bear: pd.DataFrame, n_boot=5000, seed=0) -> Symmetry:
    """Is the bullish signature the mirror image of the (sign-flipped) bearish one?

    Resamples events within each group; a difference whose interval covers zero
    is consistent with symmetry.
    """
    rng = np.random.default_rng(seed)
    sb, sr = signature(bull), signature(bear)
    keys = [k for k in sb if k != "n"]
    wb, wr = window_sums(bull).to_numpy(), window_sums(bear).to_numpy()
    cols = list(window_sums(bull).columns)
    draws = []
    for _ in range(n_boot):
        mb = wb[rng.integers(0, len(wb), len(wb))].mean(axis=0)
        mr = wr[rng.integers(0, len(wr), len(wr))].mean(axis=0)
        db, dr = dict(zip(cols, mb)), dict(zip(cols, mr))
        for d in (db, dr):
            d["speed"] = d["jump"] / d["car_0_20"] if d["car_0_20"] > 0 else np.nan
        draws.append({k: db[k] - dr[k] for k in keys})
    draws = pd.DataFrame(draws)
    diff = {k: sb[k] - sr[k] for k in keys}
    ci = {k: tuple(draws[k].quantile([0.05, 0.95])) for k in keys}
    p = {k: float(min(1.0, 2 * min((draws[k] <= 0).mean(), (draws[k] >= 0).mean())))
         for k in keys}
    return Symmetry(sb, sr, diff, ci, p)


def placebo(ret, names, market, n=500, seed=1, exclude=None) -> pd.DataFrame:
    """Window sums on random days: how big a 'signature' pure noise produces."""
    rng = np.random.default_rng(seed)
    lo, hi = -EST[0], len(ret) - POST - 1
    pool = np.arange(lo, hi)
    if exclude is not None:
        bad = np.concatenate([np.arange(p - PRE, p + POST + 1) for p in exclude])
        pool = np.setdiff1d(pool, bad)
    rows = []
    for pos in rng.choice(pool, n, replace=False):
        ar = abnormal_path(ret, int(pos), names, market)
        if ar is not None:
            rows.append(ar)
    return window_sums(pd.DataFrame(rows))
