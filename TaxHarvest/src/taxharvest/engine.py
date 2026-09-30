"""Chance-constrained selection of lots for a dollar tax-savings goal.

Notation (all per scenario s = 1..N drawn from F_P):

    l[i, s] = shares_i * max(0, basis_i - price_i,s)     loss on lot i at the harvest date
    L_s(x)  = sum_i x_i * l[i, s]                         loss realised by the plan x in [0, 1]^n
    G       = gains already realised (or explicitly expected to be realised) this tax year
    T       = desired tax saving in dollars
    K       = T / tax_rate       loss needed to save T under the flat-rate model

A plan selects maximum fractions of lots. On the harvest date, sell eligible losing shares
only until the tax-savings goal is reached; the last sale may be partial.

Methods (all minimise c'x, the size of S plus a tracking penalty for poor replacements):

    "mean"             E[L(x)] = K exactly
    "cvar"             CVaR_a(K - L) <= 0   (convex, implies P(L >= K) >= a; conservative)
    "calibrated"       "cvar" at the smallest level a' <= a whose solution still meets
                       P(L >= K) >= a in-sample (bisection) -> confidence lands on a, not above
    "milp"             exact SAA chance constraint with one binary per scenario
                       (L_s >= K z_s, sum z_s >= a N); fewer scenarios, exact in-sample
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from .model import ReturnModel, Universe
from .portfolio import Portfolio
from .washsale import Jurisdiction, LotStatus, Replacement, pick_replacements, screen

METHODS = ("calibrated", "cvar", "milp", "mean")
LP_TIME_LIMIT = 15.0  # seconds per LP


@dataclass
class HarvestProblem:
    portfolio: Portfolio
    universe: Universe
    model: ReturnModel  # daily log-return model over portfolio.tickers
    rules: Jurisdiction
    tax_rate: float
    confidence: float = 0.90
    horizon_days: int = 40  # trading days from as_of to the harvest date
    realized_gains: float = 0.0  # gains actually realised or explicitly planned this tax year
    tax_savings_goal: float | None = None  # dollars; None means the full modelled tax bill
    tracking_penalty: float = 5.0  # cost per $ sold per unit of (1 - corr) to the replacement
    n_scenarios: int = 10_000
    # extra models the plan must also satisfy (distributionally robust); name -> model
    ambiguity: dict[str, ReturnModel] = field(default_factory=dict)
    seed: int = 7
    harvest_date: date | None = None  # exact sale date; default converts horizon_days

    @property
    def harvest_on(self) -> date:
        if self.harvest_date is not None:
            return self.harvest_date
        # trading -> calendar days (252 / 365)
        return self.portfolio.as_of + timedelta(days=round(self.horizon_days * 365 / 252))


@dataclass
class Scenarios:
    losses: np.ndarray  # (n_lots, N) loss per lot if fully sold, 0 where not eligible
    raw_losses: np.ndarray  # (n_lots, N) same, ignoring eligibility
    gains: np.ndarray  # (N,) gain base G_s
    port_pnl: np.ndarray  # (N,) dollar P&L of the whole P over the horizon


def simulate(problem: HarvestProblem, n: int | None = None, rng=None,
             model: ReturnModel | None = None, eligible: np.ndarray | None = None) -> Scenarios:
    p = problem.portfolio
    model = model or problem.model
    rng = rng or np.random.default_rng(problem.seed)
    n = n or problem.n_scenarios
    R = model.sample_terminal(n, problem.horizon_days, rng)  # (N, m)
    col = {t: k for k, t in enumerate(model.tickers)}
    idx = np.array([col[lot.ticker] for lot in p.lots])
    shares = np.array([lot.shares for lot in p.lots])
    basis = np.array([lot.cost_basis for lot in p.lots])
    price0 = np.array([lot.price for lot in p.lots])
    prices = price0[:, None] * np.exp(R[:, idx].T)  # (n_lots, N)
    raw = shares[:, None] * np.clip(basis[:, None] - prices, 0, None)
    pnl_lot = shares[:, None] * (prices - price0[:, None])
    if eligible is None:
        eligible = np.ones(len(p.lots), bool)
    return Scenarios(
        losses=raw * eligible[:, None],
        raw_losses=raw,
        gains=np.full(n, problem.realized_gains),
        port_pnl=pnl_lot.sum(0),
    )


def target_from(problem: HarvestProblem) -> float:
    """Tax saving sought, never an amount of losses."""
    if problem.tax_savings_goal is not None:
        if problem.tax_savings_goal < 0:
            raise ValueError("tax_savings_goal must be nonnegative")
        return problem.tax_savings_goal
    return problem.tax_rate * max(problem.realized_gains, 0.0)


# ----------------------------------------------------------------------------- LP / MILP
# Every solver takes a *list* of loss matrices, one per model in the ambiguity set; the
# constraint must hold under each (a distributionally robust chance constraint). The usual
# case is a one-element list.
def _as_list(Lm):
    return list(Lm) if isinstance(Lm, (list, tuple)) else [Lm]


def _solve_cvar(Lms, K, alpha, c, ub):
    """min c'x  s.t. for each model m: eta_m + sum(u_m)/((1-a)N_m) <= 0,
    u_m,s >= K - L_m,s x - eta_m, u >= 0."""
    Lms = _as_list(Lms)
    n = Lms[0].shape[0]
    Ns = [L.shape[1] for L in Lms]
    M, tot = len(Lms), sum(Ns)
    # variables: x (n), eta (M), u (sum N)
    cost = np.concatenate([c, np.zeros(M + tot)])
    rows, rhs = [], []
    off = 0
    for m, L in enumerate(Lms):
        N = L.shape[1]
        eta = np.zeros((N, M))
        eta[:, m] = -1
        u = sparse.hstack([sparse.csr_matrix((N, off)), -sparse.eye(N),
                           sparse.csr_matrix((N, tot - off - N))])
        rows.append(sparse.hstack([sparse.csr_matrix(-(L / K).T), sparse.csr_matrix(eta), u]))
        rhs.append(-np.ones(N))
        cv = np.zeros(n + M + tot)
        cv[n + m] = 1
        cv[n + M + off:n + M + off + N] = 1 / ((1 - alpha) * N)
        rows.append(sparse.csr_matrix(cv))
        rhs.append([0.0])
        off += N
    A = sparse.vstack(rows).tocsr()
    bounds = [(0, u) for u in ub] + [(None, None)] * M + [(0, None)] * tot
    b = np.concatenate(rhs)
    # IPM is fast here but can stall near the feasibility boundary; retry with dual simplex,
    # and treat a second time-out as infeasible (the level search then just moves its bracket).
    res = linprog(cost, A_ub=A, b_ub=b, bounds=bounds, method="highs-ipm",
                  options={"time_limit": LP_TIME_LIMIT})
    if res.status == 1:
        res = linprog(cost, A_ub=A, b_ub=b, bounds=bounds, method="highs-ds",
                      options={"time_limit": LP_TIME_LIMIT})
    return (res.x[:n] if res.status == 0 else None), res


def _solve_mean(Lm, K, c, ub):
    m = Lm.mean(1) / K
    res = linprog(c, A_eq=m[None], b_eq=[1.0], bounds=list(zip(np.zeros_like(ub), ub)),
                  method="highs")
    return (res.x if res.status == 0 else None), res


def _solve_milp(Lms, K, alpha, c, ub, time_limit=20.0):
    Lms = _as_list(Lms)
    n = Lms[0].shape[0]
    tot = sum(L.shape[1] for L in Lms)
    cost = np.concatenate([c, np.zeros(tot)])
    # per model: L_s x - K z_s >= 0 (scaled), and sum_s z_s >= ceil(a N_m)
    A1 = sparse.hstack([sparse.csr_matrix(np.hstack([L / K for L in Lms]).T), -sparse.eye(tot)])
    cons = [LinearConstraint(A1, 0, np.inf)]
    off = 0
    for L in Lms:
        N = L.shape[1]
        row = np.zeros(n + tot)
        row[n + off:n + off + N] = 1
        cons.append(LinearConstraint(sparse.csr_matrix(row), math.ceil(alpha * N), np.inf))
        off += N
    integrality = np.concatenate([np.zeros(n), np.ones(tot)])
    bounds = Bounds(np.zeros(n + tot), np.concatenate([ub, np.ones(tot)]))
    res = milp(cost, constraints=cons, integrality=integrality, bounds=bounds,
               options={"time_limit": time_limit, "mip_rel_gap": 1e-3})
    return (res.x[:n] if res.x is not None else None), res


def coverage(Lm, x, K) -> float:
    """P(L >= K); with several models, the worst one."""
    return min(float(np.mean(x @ L >= K * (1 - 1e-9))) for L in _as_list(Lm))


def _prune_feasible_pool(Lms, K, alpha, c, ub):
    """Keep a feasible candidate pool when the CVaR approximation cannot size one."""
    x = ub.copy()
    for i in np.argsort(-c):
        if x[i] <= 0:
            continue
        x[i] = 0.0
        if coverage(Lms, x, K) >= alpha:
            continue
        lo, hi = 0.0, ub[i]
        for _ in range(12):
            x[i] = (lo + hi) / 2
            if coverage(Lms, x, K) >= alpha:
                hi = x[i]
            else:
                lo = x[i]
        x[i] = hi
    return x


def solve_x(Lm, K, alpha, c, ub, method="calibrated", milp_scenarios=1500, rng=None):
    """Return (x, info). ``Lm`` is a loss matrix or a list of them (ambiguity set)."""
    Lms = _as_list(Lm)
    n = Lms[0].shape[0]
    if K <= 0:
        return np.zeros(n), {"status": "no target (expected gains <= 0)"}
    x_all = ub.copy()
    best_cov = coverage(Lms, x_all, K)
    if method == "mean":
        if (x_all @ Lms[0]).mean() < K:
            return np.zeros(n), {"status": "infeasible: mean loss capacity below goal; no trades",
                                 "max_coverage": best_cov}
        x, res = _solve_mean(Lms[0], K, c, ub)
        return x, {"status": res.message}
    if best_cov < alpha:
        return np.zeros(n), {"status": f"infeasible: even every eligible lot reaches the "
                                   f"tax goal in only {best_cov:.1%} of scenarios; no trades",
                             "max_coverage": best_cov}
    if method == "cvar":
        x, res = _solve_cvar(Lms, K, alpha, c, ub)
        if x is None:
            return np.zeros(n), {"status": "CVaR constraint infeasible; no trades",
                                 "max_coverage": best_cov}
        return x, {"status": res.message}
    if method == "milp":
        rng = rng or np.random.default_rng(0)
        per = max(milp_scenarios // len(Lms), 200)
        subs = [L if L.shape[1] <= per else L[:, rng.choice(L.shape[1], per, replace=False)]
                for L in Lms]
        x, res = _solve_milp(subs, K, alpha, c, ub)
        if x is None:
            return np.zeros(n), {"status": f"milp failed ({res.message}); no trades",
                                 "max_coverage": best_cov}
        return x, {"status": res.message, "milp_scenarios": sum(S.shape[1] for S in subs)}
    if method == "calibrated":
        return _calibrate(Lms, K, alpha, c, ub, x_all)
    raise ValueError(f"unknown method {method!r}; choose from {METHODS}")


def _calibrate(Lms, K, alpha, c, ub, x_all, tol=0.003, max_steps=8):
    """Smallest CVaR level a' whose LP solution still has P(L >= K) >= a in-sample.

    Coverage is monotone and smooth in a', so a safeguarded regula falsi (Illinois) finds it in
    a handful of LP solves. CVaR at a itself can be infeasible (it is stricter than the chance
    constraint); the upper end of the bracket then comes from a short feasibility bisection.
    """
    solves = 0

    def f(level):
        nonlocal solves
        solves += 1
        x, _ = _solve_cvar(Lms, K, level, c, ub)
        return x, (coverage(Lms, x, K) if x is not None else None)

    hi = alpha
    x_hi, cov_hi = f(hi)
    if x_hi is None:
        lo_f, x_f, cov_f = 0.0, None, None
        for _ in range(6):
            mid = 0.5 * (lo_f + hi)
            x_mid, cov_mid = f(mid)
            if x_mid is None:
                hi = mid
            else:
                lo_f, x_f, cov_f = mid, x_mid, cov_mid
        if x_f is None:
            return np.zeros_like(x_all), {"status": "CVaR infeasible at every level; no trades"}
        hi, x_hi, cov_hi = lo_f, x_f, cov_f
    if cov_hi < alpha:  # even the tightest feasible CVaR plan misses
        return np.zeros_like(x_all), {"status": "calibration failed; no trades", "solves": solves}
    best = (x_hi, hi, cov_hi)
    lo, x_lo, cov_lo = 0.0, *f(0.0)
    if x_lo is None:
        return best[0], {"status": "optimal", "cvar_level": hi, "solves": solves}
    if cov_lo >= alpha:
        return x_lo, {"status": "optimal", "cvar_level": 0.0, "solves": solves}
    side, steps = 0, 0
    while steps < max_steps and cov_hi - alpha > tol:
        steps += 1
        g_lo, g_hi = cov_lo - alpha, cov_hi - alpha
        mid = hi - g_hi * (hi - lo) / (g_hi - g_lo)
        mid = min(max(mid, lo + 0.05 * (hi - lo)), hi - 0.05 * (hi - lo))
        x_mid, cov_mid = f(mid)
        if x_mid is not None and cov_mid >= alpha:
            hi, x_hi, cov_hi = mid, x_mid, cov_mid
            best = (x_mid, mid, cov_mid)
            if side == 1:
                cov_lo = alpha + 0.5 * (cov_lo - alpha)  # Illinois step
            side = 1
        else:
            lo, cov_lo = mid, (cov_mid if cov_mid is not None else cov_lo)
            if side == -1:
                cov_hi = alpha + 0.5 * (cov_hi - alpha)
            side = -1
    return best[0], {"status": "optimal", "cvar_level": best[1], "solves": solves}


# ----------------------------------------------------------------------------- execution
def sale_costs(lots, replacements: dict[str, Replacement], tracking_penalty: float) -> np.ndarray:
    """Market value sold, inflated by how poorly the replacement tracks the original."""
    return np.array([
        lot.value * (1 + tracking_penalty * (1 - replacements[lot.ticker].corr
                                             if lot.ticker in replacements else 1))
        for lot in lots
    ])


def allocate_losses(capacity: np.ndarray, cost: np.ndarray, target) -> np.ndarray:
    """Fill ``target`` loss per scenario column, cheapest cost per dollar of loss first.

    ``capacity`` is (n_lots, N) loss available per lot; ``target`` is a scalar or (N,).
    """
    lot_loss = capacity if capacity.ndim == 2 else capacity[:, None]
    ratio = np.divide(np.broadcast_to(cost[:, None], lot_loss.shape), lot_loss,
                      out=np.full(lot_loss.shape, np.inf), where=lot_loss > 0)
    order = np.argsort(ratio, axis=0)
    ordered = np.take_along_axis(lot_loss, order, axis=0)
    remaining = np.maximum(np.asarray(target) - (np.cumsum(ordered, axis=0) - ordered), 0)
    out = np.zeros_like(lot_loss)
    np.put_along_axis(out, order, np.minimum(ordered, remaining), axis=0)
    return out


# ----------------------------------------------------------------------------- result
@dataclass
class HarvestPlan:
    problem: HarvestProblem
    x: np.ndarray
    status: list[LotStatus]
    replacements: dict[str, Replacement]
    target: float  # tax saving the executable plan aims for, in currency units
    requested_target: float  # user goal, before any infeasibility adjustment
    loss_target: float  # loss capacity required to reach target at the flat tax rate
    losses: np.ndarray  # (N,) potential loss if all selected maximum fractions were sold
    gains: np.ndarray  # realised gain base, not mark-to-market returns
    port_pnl: np.ndarray
    lot_losses: np.ndarray  # (n_lots, N) eligible
    tracking_error: float  # $ 1-sd over the 31-day replacement window
    info: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def confidence(self) -> float:
        return float(np.mean(self.tax_savings >= self.target * (1 - 1e-9)))

    @property
    def realized_losses(self) -> np.ndarray:
        """Execution stops at the loss needed for the tax-savings goal."""
        return np.minimum(self.losses, self.loss_target)

    @property
    def tax_savings(self) -> np.ndarray:
        return self.problem.tax_rate * np.minimum(self.realized_losses,
                                                  np.maximum(self.gains, 0.0))

    @property
    def expected_loss(self) -> float:
        return float(self.realized_losses.mean())

    @property
    def expected_unused_capacity(self) -> float:
        return float(np.maximum(self.losses - self.realized_losses, 0.0).mean())

    @property
    def expected_market_sold(self) -> float:
        executed = self.executed_lot_losses()
        fractions = np.divide(executed, self.lot_losses,
                              out=np.zeros_like(executed), where=self.lot_losses > 0)
        values = np.array([lot.value for lot in self.problem.portfolio.lots])
        return float((values[:, None] * fractions).sum(0).mean())

    @property
    def expected_tax_saved(self) -> float:
        """This year's saving: tax(G) - tax(G - L); losses beyond G carry forward, not counted."""
        return float(self.tax_savings.mean())

    def executed_lot_losses(self) -> np.ndarray:
        """Scenario-wise sale allocation: cheapest replacement-adjusted loss first."""
        if self.loss_target <= 0 or not np.any(self.x):
            return np.zeros_like(self.lot_losses)
        cost = sale_costs(self.problem.portfolio.lots, self.replacements,
                          self.problem.tracking_penalty)
        return allocate_losses(self.x[:, None] * self.lot_losses, cost, self.loss_target)

    def execute(self, prices: dict[str, float]) -> pd.DataFrame:
        """Size actual sales at the harvest date, stopping at the tax goal.

        Prices must cover every selected ticker. Fractional shares are kept to six decimal
        places, rounded down so execution cannot exceed the desired loss amount.
        """
        columns = ("lot", "ticker", "account", "acquired", "sell_shares", "sell_price",
                   "realized_loss", "tax_saved", "replace_with", "buy_back_from")
        candidates = []
        for i, (xi, lot) in enumerate(zip(self.x, self.problem.portfolio.lots)):
            if xi <= 0:
                continue
            if lot.ticker not in prices:
                raise ValueError(f"missing harvest-date price for {lot.ticker}")
            price = float(prices[lot.ticker])
            if price <= 0:
                raise ValueError(f"invalid harvest-date price for {lot.ticker}")
            loss_per_share = max(lot.cost_basis - price, 0.0)
            if loss_per_share <= 0:
                continue
            rep = self.replacements.get(lot.ticker)
            cost = sale_costs([lot], self.replacements, self.problem.tracking_penalty)[0]
            candidates.append((cost / (lot.shares * loss_per_share), i, lot, price,
                               loss_per_share, rep, xi))
        rows = []
        remaining = self.loss_target
        for _, i, lot, price, loss_per_share, rep, xi in sorted(candidates):
            if remaining <= 0:
                break
            shares = min(xi * lot.shares, remaining / loss_per_share)
            shares = math.floor(shares * 1e6) / 1e6
            if shares <= 0:
                continue
            loss = shares * loss_per_share
            remaining -= loss
            rows.append({
                "lot": i, "ticker": lot.ticker, "account": lot.account,
                "acquired": lot.acquired, "sell_shares": shares, "sell_price": price,
                "realized_loss": loss, "tax_saved": self.problem.tax_rate * loss,
                "replace_with": rep.buy if rep else "",
                "buy_back_from": rep.buy_back_from if rep else None,
            })
        orders = pd.DataFrame(rows, columns=columns)
        saved = float(orders.tax_saved.sum())
        orders.attrs.update({"tax_savings_goal": self.target, "tax_saved": saved,
                             "shortfall": max(self.target - saved, 0.0),
                             "goal_met": saved >= self.target - 0.01})
        return orders

    @property
    def subportfolio_value(self) -> float:
        return float(sum(x * lot.value for x, lot in zip(self.x, self.problem.portfolio.lots)))

    def trades(self) -> pd.DataFrame:
        p = self.problem.portfolio
        executed = self.executed_lot_losses()
        executed_frac = np.divide(executed, self.lot_losses,
                                  out=np.zeros_like(executed), where=self.lot_losses > 0)
        rows = []
        for i, lot in enumerate(p.lots):
            st = self.status[i]
            rep = self.replacements.get(lot.ticker)
            rows.append({
                "lot": i,
                "account": lot.account,
                "ticker": lot.ticker,
                "acquired": lot.acquired,
                "value": lot.value,
                "unrealized": lot.unrealized,
                "eligible": st.eligible,
                "max_sell_frac": round(float(self.x[i]), 6),
                "max_sell_shares": math.floor(self.x[i] * lot.shares * 1e6) / 1e6,
                "E[loss]": float(executed[i].mean()),
                "E[loss capacity]": float(self.x[i] * self.lot_losses[i].mean()),
                "E[sell shares]": float(lot.shares * executed_frac[i].mean()),
                "P(in loss)": float(np.mean(self.lot_losses[i] > 0)) if st.eligible else np.nan,
                "replace_with": rep.buy if (rep and self.x[i] > 1e-6) else "",
                "corr": rep.corr if (rep and self.x[i] > 1e-6) else np.nan,
                "buy_back_from": rep.buy_back_from if (rep and self.x[i] > 1e-6) else None,
                "why_not": "; ".join(st.reasons),
            })
        return pd.DataFrame(rows)

    def summary(self) -> dict:
        q = np.quantile(self.realized_losses, [0.05, 0.5, 0.95])
        return {
            "jurisdiction": self.problem.rules.code,
            "harvest_on": self.problem.harvest_on,
            "tax_rate": self.problem.tax_rate,
            "realized gain base": float(self.gains.mean()),
            "requested tax saving goal": self.requested_target,
            "tax saving goal": self.target,
            "max reliable tax saving": self.info.get("max_reliable_tax_saving"),
            "loss needed for goal": self.loss_target,
            "confidence (target)": self.problem.confidence,
            "P(tax saved >= goal) in-sample": self.confidence,
            "E[loss capacity]": float(self.losses.mean()),
            "E[loss realized]": self.expected_loss,
            "E[unused loss capacity]": self.expected_unused_capacity,
            "E[market sold at current prices]": self.expected_market_sold,
            "realized loss 5/50/95%": tuple(float(v) for v in q),
            "E[tax saved]": self.expected_tax_saved,
            "sub-portfolio value": self.subportfolio_value,
            "sub-portfolio share of P": self.subportfolio_value / self.problem.portfolio.value,
            "tracking error 31d ($, 1sd)": self.tracking_error,
            "status": self.info.get("status"),
            "seconds": round(self.seconds, 2),
        }


def _tracking_error(problem, x, replacements):
    p, uni = problem.portfolio, problem.universe
    diff: dict[str, float] = {}
    for xi, lot in zip(x, p.lots):
        rep = replacements.get(lot.ticker)
        if xi <= 1e-9 or rep is None:
            continue
        diff[lot.ticker] = diff.get(lot.ticker, 0.0) - xi * lot.value
        diff[rep.buy] = diff.get(rep.buy, 0.0) + xi * lot.value
    if not diff:
        return 0.0
    tick = list(diff)
    w = np.array([diff[t] for t in tick])
    cov = uni.factor_model(tick).cov
    return float(np.sqrt(w @ cov @ w * 21))  # 31 calendar days ~ 21 trading days


def optimise(problem: HarvestProblem, method: str = "calibrated") -> HarvestPlan:
    t0 = time.perf_counter()
    if problem.tax_rate < 0 or not 0 < problem.confidence < 1:
        raise ValueError("tax_rate must be nonnegative and confidence must be between 0 and 1")
    p, uni = problem.portfolio, problem.universe
    status = screen(p, uni, problem.harvest_on, problem.rules)
    eligible = np.array([s.eligible for s in status])
    sc = simulate(problem, eligible=eligible)
    requested_target = target_from(problem)
    tax_bill = problem.tax_rate * max(problem.realized_gains, 0.0)

    # linear cost: $ sold (normalised) + tracking penalty from the best replacement's corr
    cov_lookup = lambda ts: uni.factor_model(ts).cov
    pre = pick_replacements(p.tickers, uni, cov_lookup, problem.harvest_on, problem.rules, set())
    V = p.value
    c = np.array([
        lot.value / V * (1 + problem.tracking_penalty * (1 - pre[lot.ticker].corr
                                                         if lot.ticker in pre else 1))
        for lot in p.lots
    ])
    ub = eligible & (sc.losses.max(1) > 0)
    ub = ub.astype(float)

    Lms = [sc.losses]
    for k, m in enumerate(problem.ambiguity.values()):
        Lms.append(simulate(problem, rng=np.random.default_rng(problem.seed + 100 + k), model=m,
                            eligible=eligible).losses)
    reliable_loss = min(float(np.quantile(ub @ L, 1 - problem.confidence,
                                           method="lower")) for L in Lms)
    max_reliable_goal = min(tax_bill, problem.tax_rate * reliable_loss)
    reduced = requested_target > max_reliable_goal + 1e-9
    target = min(requested_target, 0.98 * max_reliable_goal) if reduced else requested_target
    K = target / problem.tax_rate if problem.tax_rate > 0 else 0.0
    if target <= 0:
        x = np.zeros(len(p.lots))
        info = {"status": "no attainable tax-saving goal; no trades"}
    else:
        x, info = solve_x(Lms, K, problem.confidence, c, ub, method,
                          rng=np.random.default_rng(problem.seed + 1))
        if not np.any(x) and coverage(Lms, ub, K) >= problem.confidence:
            x = _prune_feasible_pool(Lms, K, problem.confidence, c, ub)
            info["status"] = ("solver could not size the pool; using a feasible, "
                              "greedily reduced candidate pool with sales capped at the goal")
    if reduced:
        info["status"] = (f"requested tax-saving goal {requested_target:,.2f} is infeasible "
                          f"at {problem.confidence:.0%} confidence; {info['status']}; "
                          f"planning for {target:,.2f} instead")
    info["max_reliable_tax_saving"] = max_reliable_goal
    if problem.ambiguity:
        info["worst-case P(tax saved >= goal) over ambiguity set"] = (
            coverage(Lms, x, K) if K > 0 else 1.0)
    x = np.where(x > 1e-7, np.minimum(x, 1.0), 0.0)
    if problem.tax_rate == 0 and problem.tax_savings_goal is None:
        info["status"] = (f"nothing to harvest: gains are untaxed under {problem.rules.name} "
                          f"rules, so a loss saves nothing")

    harvested_groups = {uni.group(lot.ticker) for xi, lot in zip(x, p.lots) if xi > 0}
    sold = sorted({lot.ticker for xi, lot in zip(x, p.lots) if xi > 0})
    reps = pick_replacements(sold, uni, cov_lookup, problem.harvest_on, problem.rules,
                             harvested_groups)
    plan = HarvestPlan(
        problem=problem, x=x, status=status, replacements=reps,
        target=target, requested_target=requested_target, loss_target=K,
        losses=x @ sc.losses, gains=sc.gains, port_pnl=sc.port_pnl, lot_losses=sc.losses,
        tracking_error=_tracking_error(problem, x, reps), info=info,
    )
    plan.seconds = time.perf_counter() - t0
    return plan


def evaluate(plan: HarvestPlan, n: int, rng, model: ReturnModel | None = None) -> dict:
    """Fresh-scenario (out-of-sample) performance of a fixed plan, optionally under another F."""
    eligible = np.array([s.eligible for s in plan.status])
    sc = simulate(plan.problem, n=n, rng=rng, model=model, eligible=eligible)
    L = plan.x @ sc.losses
    realized = np.minimum(L, plan.loss_target)
    saved = plan.problem.tax_rate * np.minimum(realized, np.maximum(sc.gains, 0.0))
    return {"confidence": float(np.mean(saved >= plan.target * (1 - 1e-9))),
            "E[loss realized]": float(realized.mean()), "E[tax saved]": float(saved.mean()),
            "losses": L, "realized_losses": realized, "tax_savings": saved}
