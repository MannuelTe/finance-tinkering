"""Walk-forward backtest of the drift after uranium news.

The rule only uses what was known before each trade:

* The trade is entered at the close of day +1, after the jump, in the news
  direction, and exited at the close of day +HOLD. The position is the uranium
  basket hedged with its market-model betas, so its P&L is the signed abnormal
  return over days 2..HOLD.
* It is taken only if the average drift of *earlier* events of the same
  direction, over the same days, beat the round-trip cost. Before MIN_PRIOR
  earlier events exist, nothing is traded.

Costs: COST_BP per side on the basket, plus short-borrow on short legs.

The caveat that no backtest here can remove: the events were picked and signed
by hand, after the fact. A live version would have to classify news as it
arrives, and a catalog of memorable events favours news that moved prices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HOLD = 20
MIN_PRIOR = 5
COST_BP = 10.0          # per side, equity basket
BORROW = 0.02           # annual, charged on short legs


def trades(ar: pd.DataFrame, kept: pd.DataFrame, hold=HOLD, min_prior=MIN_PRIOR,
           cost_bp=COST_BP, borrow=BORROW) -> pd.DataFrame:
    """One row per event: whether the rule traded it, and its net P&L."""
    drift = ar.loc[:, 2:hold].sum(axis=1).to_numpy()
    order = np.argsort(pd.to_datetime(kept["day0"]).to_numpy(), kind="stable")
    rt_cost = 2 * cost_bp / 1e4
    rows = []
    for i in order:
        d0, direction = kept["day0"].iloc[i], kept["direction"].iloc[i]
        prior = [j for j in order
                 if kept["direction"].iloc[j] == direction
                 and pd.Timestamp(kept["day0"].iloc[j]) + pd.tseries.offsets.BDay(hold)
                 < pd.Timestamp(d0)]
        # side of the trade in price terms: +1 long, -1 short
        side = 1 if direction == "bull" else -1
        cost = rt_cost + (borrow * (hold - 1) / 252 if side < 0 else 0)
        expected = drift[prior].mean() if len(prior) >= min_prior else np.nan
        take = bool(expected > cost) if not np.isnan(expected) else False
        rows.append({"day0": d0, "label": kept["label"].iloc[i], "direction": direction,
                     "n_prior": len(prior), "expected": expected, "taken": take,
                     "gross": drift[i], "net": drift[i] - cost if take else 0.0})
    return pd.DataFrame(rows)


def summary(t: pd.DataFrame) -> dict:
    x = t.loc[t.taken, "net"]
    n = len(x)
    return {"trades": n, "hit_rate": (x > 0).mean() if n else np.nan,
            "mean_net": x.mean() if n else np.nan,
            "t_stat": x.mean() / x.std(ddof=1) * np.sqrt(n) if n > 1 else np.nan,
            "total_net": x.sum()}


def random_baseline(ret, names, market, n_trades, hold=HOLD, n_sims=2000, seed=2,
                    exclude=None, cost_bp=COST_BP):
    """Same number of trades on random days in a random direction: what luck gives."""
    from . import study

    noise = study.placebo(ret, names, market, n=1500, seed=seed, exclude=exclude)
    drift = noise["drift"].to_numpy() if hold == 20 else None
    rng = np.random.default_rng(seed)
    means = [(rng.choice([-1, 1], n_trades) * rng.choice(drift, n_trades)).mean()
             - 2 * cost_bp / 1e4 for _ in range(n_sims)]
    return np.array(means)
