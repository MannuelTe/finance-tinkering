"""Daily re-planning: wait while waiting is safe enough, lock losses in when it is not.

The one-shot plan fixes a sale date and asks whether enough loss will still exist then. A
daily review asks the same question again each day with fresh prices, what has already been
harvested, and what gains have been realized:

    K_rem          = loss still needed (goal minus losses already harvested, at most the gains left)
    P_wait         = P(eligible losses on the deadline >= K_rem), simulated from today's prices
    action         = sell today, up to K_rem, when P_wait < trigger (default: the confidence)
                     or on the deadline itself; otherwise hold

Selling today makes the harvested part certain. Waiting keeps the position invested, and a
later sale can reach the same loss with fewer shares if prices fall further; it can also miss
if they recover. The backtest runs these rules on the same simulated price paths.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .engine import (
    HarvestPlan,
    HarvestProblem,
    allocate_losses,
    coverage,
    optimise,
    sale_costs,
    simulate,
)
from .model import ReturnModel, Universe
from .portfolio import Portfolio
from .washsale import Jurisdiction, pick_replacements, screen


def trading_days(start: date, end: date) -> int:
    """Weekdays from ``start`` (exclusive) to ``end`` (inclusive); holidays are ignored."""
    return max(int(np.busday_count(start + pd.Timedelta(days=1), end + pd.Timedelta(days=1))), 0)


def year_end(as_of: date) -> date:
    """Last weekday of the tax year."""
    return pd.Timestamp(np.busday_offset(date(as_of.year, 12, 31), 0, roll="backward")).date()


def loss_goal(tax_rate: float, realized_gains: float, tax_savings_goal: float | None) -> float:
    """Losses needed for the goal; losses beyond this year's gains save nothing now."""
    gains = max(realized_gains, 0.0)
    if tax_savings_goal is None:
        return gains
    if tax_rate <= 0:
        return 0.0
    return min(tax_savings_goal / tax_rate, gains)


@dataclass
class Review:
    as_of: date
    deadline: date
    days_left: int
    tax_rate: float
    confidence: float
    loss_goal: float  # K for the whole year
    harvested: float  # losses already realized this year
    available_today: float  # eligible losses if sold today
    wait_confidence: float  # P(eligible losses on the deadline >= remaining)
    action: str  # "done", "hold" or "sell"
    orders: pd.DataFrame = field(default_factory=pd.DataFrame)
    pool: HarvestPlan | None = None  # lots to keep available while holding
    every: int = 1  # trading days between reviews (5 = weekly)

    @property
    def next_review(self) -> date | None:
        if self.action == "done" or self.days_left == 0:
            return None
        nxt = pd.Timestamp(np.busday_offset(self.as_of, self.every, roll="forward")).date()
        return min(nxt, self.deadline)

    @property
    def remaining(self) -> float:
        return max(self.loss_goal - self.harvested, 0.0)

    @property
    def progress(self) -> float:
        """Share of the loss goal already locked in."""
        return self.harvested / self.loss_goal if self.loss_goal > 0 else 1.0

    @property
    def cover(self) -> float:
        """Losses available today per dollar still needed; >= 1 means today could finish it."""
        return self.available_today / self.remaining if self.remaining > 0 else math.inf

    def row(self) -> dict:
        sold = float(self.orders.realized_loss.sum()) if len(self.orders) else 0.0
        return {
            "date": self.as_of.isoformat(), "deadline": self.deadline.isoformat(),
            "days_left": self.days_left, "loss_goal": round(self.loss_goal, 2),
            "harvested": round(self.harvested, 2), "remaining": round(self.remaining, 2),
            "progress": round(self.progress, 4), "available_today": round(self.available_today, 2),
            "cover": round(self.cover, 4) if math.isfinite(self.cover) else "",
            "wait_confidence": round(self.wait_confidence, 4),
            "trigger": self.confidence, "action": self.action, "sell_loss": round(sold, 2),
            "next_review": self.next_review.isoformat() if self.next_review else "",
        }


def review(portfolio: Portfolio, universe: Universe, model: ReturnModel, rules: Jurisdiction, *,
           realized_gains: float, harvested_loss: float = 0.0,
           tax_savings_goal: float | None = None, tax_rate: float | None = None,
           deadline: date | None = None, confidence: float = 0.90,
           trigger: float | None = None, every: int = 1, tracking_penalty: float = 5.0,
           n_scenarios: int = 10_000, seed: int = 7, size_pool: bool = True) -> Review:
    """One day's decision. ``portfolio`` holds today's lots and prices; ``realized_gains``
    are this year's gains before any harvested losses, ``harvested_loss`` the losses already
    realized."""
    tax_rate = rules.default_tax_rate if tax_rate is None else tax_rate
    deadline = deadline or year_end(portfolio.as_of)
    trigger = confidence if trigger is None else trigger
    days = trading_days(portfolio.as_of, deadline)
    K = loss_goal(tax_rate, realized_gains, tax_savings_goal)
    rem = max(K - harvested_loss, 0.0)

    lots = portfolio.lots
    today = np.array([s.eligible for s in screen(portfolio, universe, portfolio.as_of, rules)])
    loss_now = np.array([lot.shares * max(lot.cost_basis - lot.price, 0.0) for lot in lots])
    available = float((loss_now * today).sum())
    base = Review(portfolio.as_of, deadline, days, tax_rate, confidence, K, harvested_loss,
                  available, 1.0, "done", every=every)
    if rem <= 0:
        return base

    problem = HarvestProblem(
        portfolio, universe, model, rules, tax_rate=tax_rate, confidence=confidence,
        horizon_days=max(days, 1), realized_gains=realized_gains - harvested_loss,
        tax_savings_goal=tax_rate * rem, tracking_penalty=tracking_penalty,
        n_scenarios=n_scenarios, seed=seed, harvest_date=deadline)
    if days > 0:
        later = np.array([s.eligible for s in screen(portfolio, universe, deadline, rules)])
        sc = simulate(problem, eligible=later)
        base.wait_confidence = coverage(sc.losses, np.ones(len(lots)), rem)
    else:
        base.wait_confidence = 0.0
    if days > 0 and base.wait_confidence >= trigger:
        base.action = "hold"
        if size_pool:
            base.pool = optimise(problem)
        return base
    base.action = "sell"
    base.orders = sell_today(portfolio, universe, rules, today * loss_now, rem, tax_rate,
                             tracking_penalty)
    return base


def sell_today(portfolio: Portfolio, universe: Universe, rules: Jurisdiction,
               lot_loss: np.ndarray, remaining: float, tax_rate: float,
               tracking_penalty: float) -> pd.DataFrame:
    """Orders that realize up to ``remaining`` of today's eligible loss, cheapest first."""
    lots, as_of = portfolio.lots, portfolio.as_of
    cov_lookup = lambda ts: universe.factor_model(ts).cov
    pre = pick_replacements(portfolio.tickers, universe, cov_lookup, as_of, rules, set())
    executed = allocate_losses(lot_loss, sale_costs(lots, pre, tracking_penalty), remaining)[:, 0]
    sold = [i for i in np.argsort(-executed) if executed[i] > 0]
    groups = {universe.group(lots[i].ticker) for i in sold}
    reps = pick_replacements(sorted({lots[i].ticker for i in sold}), universe, cov_lookup, as_of,
                             rules, groups)
    rows = []
    for i in sold:
        lot = lots[i]
        per_share = lot.cost_basis - lot.price
        shares = math.floor(executed[i] / per_share * 1e6) / 1e6
        rep = reps.get(lot.ticker)
        rows.append({
            "lot": i, "ticker": lot.ticker, "account": lot.account, "acquired": lot.acquired,
            "sell_shares": shares, "sell_price": lot.price, "realized_loss": shares * per_share,
            "tax_saved": tax_rate * shares * per_share, "replace_with": rep.buy if rep else "",
            "buy_back_from": rep.buy_back_from if rep else None,
        })
    return pd.DataFrame(rows, columns=["lot", "ticker", "account", "acquired", "sell_shares",
                                       "sell_price", "realized_loss", "tax_saved",
                                       "replace_with", "buy_back_from"])


def append_log(path: Path, rev: Review) -> None:
    """One row per review; a rerun on the same date replaces that date's row."""
    row = rev.row()
    rows = []
    if path.exists():
        with path.open() as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != row["date"]]
    rows.append(row)
    rows.sort(key=lambda r: r["date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerows(rows)


def describe(rev: Review, cur: str = "$") -> str:
    lines = [
        f"{rev.as_of}: {rev.days_left} trading days to {rev.deadline}",
        (f"  loss goal {cur}{rev.loss_goal:,.0f}  harvested {cur}{rev.harvested:,.0f} "
         f"({rev.progress:.0%})  still needed {cur}{rev.remaining:,.0f}"),
    ]
    if rev.action == "done":
        return "\n".join(lines + ["  goal reached: nothing to sell"])
    nxt = f"  next review: {rev.next_review}" if rev.next_review else ""
    lines.append(f"  eligible loss today {cur}{rev.available_today:,.0f}  (cover {rev.cover:.2f}x)")
    if rev.days_left > 0:
        lines.append(f"  P(enough loss if you wait to the deadline) = {rev.wait_confidence:.1%}  "
                     f"(trigger {rev.confidence:.0%})")
    if rev.action == "hold":
        lines.append("  HOLD: waiting is still within your confidence")
        if rev.pool is not None:
            keep = [f"{lot.ticker} {lot.account}" for x, lot in
                    zip(rev.pool.x, rev.pool.problem.portfolio.lots) if x > 0]
            if keep:
                lines.append(f"  keep available (no conflicting buys): {', '.join(keep)}")
        return "\n".join(lines + [nxt])
    sold = float(rev.orders.realized_loss.sum()) if len(rev.orders) else 0.0
    why = "deadline" if rev.days_left == 0 else "waiting is below your confidence"
    lines.append(f"  SELL today ({why}): lock in {cur}{sold:,.0f} of losses")
    for r in rev.orders.itertuples():
        rep = f" -> buy {r.replace_with}" if r.replace_with else ""
        lines.append(f"    sell {r.sell_shares:,.4f} {r.ticker} ({r.account}) at "
                     f"{cur}{r.sell_price:,.2f}: loss {cur}{r.realized_loss:,.0f}{rep}")
    if sold < rev.remaining - 0.01:
        lines.append(f"  still short {cur}{rev.remaining - sold:,.0f} after today's sales")
    return "\n".join(lines + ([nxt] if nxt and sold < rev.remaining - 0.01 else []))


# ----------------------------------------------------------------------------- backtest
def backtest(problem: HarvestProblem, triggers: dict[str, float | tuple[float, int]],
             n_paths: int = 1000,
             n_inner: int = 2000, pool: np.ndarray | None = None, seed: int = 11) -> dict:
    """Run daily rules on the same simulated price paths up to the problem's harvest date.

    ``triggers`` maps a rule name to its threshold, or to ``(threshold, every)`` to review only
    every ``every`` trading days (5 = weekly; the deadline is always a review day). Sell when
    P_wait < threshold (1.01 means sell at the first chance, -1 means wait for the deadline).
    ``pool`` optionally limits the deadline sale to the one-shot plan's maximum fractions.
    """
    p, uni, rules = problem.portfolio, problem.universe, problem.rules
    lots, days = p.lots, problem.horizon_days
    K = loss_goal(problem.tax_rate, problem.realized_gains, problem.tax_savings_goal)
    rng = np.random.default_rng(seed)
    col = {t: k for k, t in enumerate(problem.model.tickers)}
    idx = np.array([col[lot.ticker] for lot in lots])
    shares0 = np.array([lot.shares for lot in lots])
    basis = np.array([lot.cost_basis for lot in lots])
    price0 = np.array([lot.price for lot in lots])
    paths = problem.model.sample_paths(n_paths, days, rng)[:, :, idx]
    prices = price0 * np.exp(np.concatenate([np.zeros((n_paths, 1, len(lots))), paths], 1))
    dates = [pd.Timestamp(np.busday_offset(p.as_of, t, roll="forward")).date()
             for t in range(days + 1)]
    deadline = problem.harvest_on
    elig_on = [np.array([s.eligible for s in screen(p, uni, d, rules)]) for d in dates[:-1]]
    elig_on.append(np.array([s.eligible for s in screen(p, uni, deadline, rules)]))
    inner = [None] + [problem.model.sample_terminal(n_inner, h, rng)[:, idx]
                      for h in range(1, days + 1)]
    cov_lookup = lambda ts: uni.factor_model(ts).cov
    reps = pick_replacements(p.tickers, uni, cov_lookup, deadline, rules, set())
    weight = sale_costs(lots, reps, problem.tracking_penalty) / np.array([lot.value for lot in lots])

    out = {}
    for name, spec in triggers.items():
        trigger, every = spec if isinstance(spec, tuple) else (spec, 1)
        held = np.tile(shares0, (n_paths, 1))
        H = np.zeros(n_paths)
        sold_value = np.zeros(n_paths)
        first = np.full(n_paths, -1)
        sale_days = np.zeros(n_paths, int)
        for t in range(days + 1):
            h = days - t
            if h > 0 and t % every:
                continue
            P = prices[:, t]
            rem = K - H
            active = rem > 1e-6
            if not active.any():
                break
            if h == 0 or trigger > 1:
                sell = active
            elif trigger < 0:
                sell = np.zeros(n_paths, bool)
            else:
                conf = np.ones(n_paths)
                for a in np.array_split(np.flatnonzero(active), max(1, active.sum() // 100)):
                    fut = P[a, None, :] * np.exp(inner[h][None])
                    L = (held[a, None] * np.clip(basis - fut, 0, None) * elig_on[-1]).sum(-1)
                    conf[a] = (L >= rem[a, None]).mean(1)
                sell = active & (conf < trigger)
            if not sell.any():
                continue
            per_share = np.clip(basis - P[sell], 0, None)
            cap = held[sell] * per_share * elig_on[t]
            if h == 0 and pool is not None:
                cap = np.minimum(cap, pool * shares0 * per_share)
            cost = held[sell] * P[sell] * weight
            ex = np.stack([allocate_losses(cap[j], cost[j], rem[sell][j])[:, 0]
                           for j in range(sell.sum())])
            q = np.divide(ex, per_share, out=np.zeros_like(ex), where=per_share > 0)
            held[sell] -= q
            H[sell] += ex.sum(1)
            sold_value[sell] += (q * P[sell]).sum(1)
            did = np.zeros(n_paths, bool)
            did[sell] = ex.sum(1) > 0
            first[did & (first < 0)] = t
            sale_days += did
        saved = problem.tax_rate * np.minimum(H, max(problem.realized_gains, 0.0))
        out[name] = {
            "trigger": trigger, "every": every, "P(goal met)": float(np.mean(H >= K - 0.01)),
            "E[tax saved]": float(saved.mean()), "E[market value sold]": float(sold_value.mean()),
            "P(sold before deadline)": float(np.mean((first >= 0) & (first < days))),
            "E[sale days]": float(sale_days.mean()),
            "median sale day": float(np.median(first[first >= 0])) if (first >= 0).any() else None,
            "tax_saved": saved, "sold_value": sold_value, "first_sale_day": first,
        }
    out["_meta"] = {"loss_goal": K, "days": days, "n_paths": n_paths, "n_inner": n_inner}
    return out
