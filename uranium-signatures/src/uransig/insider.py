"""Pre-announcement footprints: did prices or volume move before the news was public?

Same screen as market-surveillance/ (Meulbroek-style): over the ten sessions before
day 0, measure

    car_t  = signed CAR(-10,-1) / (residual sd * sqrt(10))   price moved the news' way
    vol_z  = (mean log volume in -10..-1  -  its estimation mean) / estimation sd

and flag an event when car_t >= 3 and vol_z >= 2. A flag is a reason to look, not
evidence: leaks to the press, rumours, sector news and imprecise timestamps look the same.

Two instruments per event:

* basket: the uranium proxies, signed by the news direction;
* direct: the security an informed person would most naturally trade (the utility that
  closes a plant, Centrus for enrichment news...), signed by that security's own
  day 0-1 reaction, because a closure can be good news for the utility.

Random non-event days scored the same way give the false-flag rate, and events nobody
could know in advance (an earthquake, a public vote) are a natural control group.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .study import EST, MIN_EST, align

WINDOW = (-10, -1)
REACTION = (0, 1)
CAR_T_MIN, VOL_Z_MIN = 3.0, 2.0
BASKET_MARKET = ("SPY", "XLE")
DIRECT_MARKET = ("SPY", "XLE", "XLU")


def footprint(ret, lvol, pos, names, market) -> dict | None:
    """Unsigned footprint of an equal-weight position in `names` around position `pos`."""
    lo, hi = pos + EST[0], pos + EST[1]
    w0, w1 = pos + WINDOW[0], pos + WINDOW[1] + 1
    r0, r1 = pos + REACTION[0], pos + REACTION[1] + 1
    if lo < 0 or r1 > len(ret):
        return None
    M = ret[list(market)].to_numpy()
    resid, ar_w, ar_r, vz, vsd = [], [], [], [], []
    for n in names:
        y = ret[n].to_numpy()
        ok = ~np.isnan(y[lo:hi]) & ~np.isnan(M[lo:hi]).any(axis=1)
        if ok.sum() < MIN_EST or np.isnan(y[w0:r1]).any():
            continue
        X = np.column_stack([np.ones(hi - lo), M[lo:hi]])
        b, *_ = np.linalg.lstsq(X[ok], y[lo:hi][ok], rcond=None)

        def pred(a, z, b=b):
            return b[0] + M[a:z] @ b[1:]

        e = np.full(hi - lo, np.nan)
        e[ok] = y[lo:hi][ok] - pred(lo, hi)[ok]
        resid.append(e)
        ar_w.append(y[w0:w1] - pred(w0, w1))
        ar_r.append(y[r0:r1] - pred(r0, r1))
        lv = lvol[n].to_numpy()
        est_v, win_v = lv[lo:hi], lv[w0:w1]
        est_v = est_v[~np.isnan(est_v)]
        if len(est_v) >= MIN_EST and not np.isnan(win_v).any() and est_v.std() > 0:
            vz.append((win_v.mean() - est_v.mean()) / est_v.std(ddof=1))
            vsd.append(est_v.std(ddof=1))
    if not resid:
        return None
    sd10 = np.nanstd(np.nanmean(resid, axis=0), ddof=1) * np.sqrt(WINDOW[1] - WINDOW[0] + 1)
    car = float(np.mean(ar_w, axis=0).sum())
    return {"car": car, "car_t": car / sd10,
            "vol_z": float(np.mean(vz)) if vz else np.nan,
            "reaction": float(np.mean(ar_r, axis=0).sum()),
            # detection limits: smallest run-up and volume multiple that could be flagged
            "min_runup": CAR_T_MIN * sd10,
            "min_vol_x": float(np.exp(VOL_Z_MIN * np.mean(vsd))) if vsd else np.nan}


def _signed(fp: dict, sign: float) -> dict:
    return {**fp, "car": sign * fp["car"], "car_t": sign * fp["car_t"],
            "reaction": sign * fp["reaction"], "sign": sign,
            "flag": bool(sign * fp["car_t"] >= CAR_T_MIN and fp["vol_z"] >= VOL_Z_MIN)}


def log_volume(vol: pd.DataFrame, index) -> pd.DataFrame:
    return np.log1p(vol.reindex(index).where(vol.reindex(index) > 0))


def screen(ret, vol, events, basket) -> pd.DataFrame:
    """One row per (signed event, instrument)."""
    lvol = log_volume(vol, ret.index)
    ev = events[events.direction != "none"].reset_index(drop=True)
    rows = []
    for (_, e), pos in zip(ev.iterrows(), align(ev["date"], ret.index, ev["session"])):
        base = {"day0": ret.index[pos].date(), "label": e["label"], "direction": e["direction"],
                "knowable": e["knowable"], "timing": e["timing"]}
        fp = footprint(ret, lvol, pos, basket, BASKET_MARKET)
        if fp:
            rows.append({**base, "instrument": "basket", **_signed(fp, e["sign"])})
        if e["direct"]:
            fp = footprint(ret, lvol, pos, [e["direct"]], DIRECT_MARKET)
            if fp:
                s = 1.0 if fp["reaction"] >= 0 else -1.0
                rows.append({**base, "instrument": e["direct"], **_signed(fp, s)})
    return pd.DataFrame(rows)


def placebo(ret, vol, names, market, n=400, seed=3, exclude=(), direct=False) -> pd.DataFrame:
    """The same screen on random days away from any event. Basket placebos get a random
    news sign; direct placebos are signed by their own day 0-1 move, like real events."""
    rng = np.random.default_rng(seed)
    lvol = log_volume(vol, ret.index)
    first = max(ret[list(names)].apply(pd.Series.first_valid_index))
    start = max(-EST[0], ret.index.get_loc(first) - EST[0] // 2)
    pool = np.arange(start, len(ret) - REACTION[1] - 1)
    if len(exclude):
        bad = np.concatenate([np.arange(p - 20, p + 21) for p in exclude])
        pool = np.setdiff1d(pool, bad)
    rows = []
    for pos in rng.choice(pool, min(n, len(pool)), replace=False):
        fp = footprint(ret, lvol, int(pos), list(names), market)
        if fp is None:
            continue
        s = (1.0 if fp["reaction"] >= 0 else -1.0) if direct else rng.choice([-1.0, 1.0])
        rows.append(_signed(fp, s))
    return pd.DataFrame(rows)


def permutation_p(x: np.ndarray, y: np.ndarray, n=10000, seed=4) -> float:
    """One-sided p-value that mean(x) > mean(y) by chance, shuffling group labels."""
    rng = np.random.default_rng(seed)
    obs = x.mean() - y.mean()
    z = np.concatenate([x, y])
    hits = 0
    for _ in range(n):
        rng.shuffle(z)
        hits += z[:len(x)].mean() - z[len(x):].mean() >= obs
    return (hits + 1) / (n + 1)
