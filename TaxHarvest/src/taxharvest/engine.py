"""Chance-constrained selection of the harvest sub-portfolio S from P.

Notation (all per scenario s = 1..N drawn from F_P):

    l[i, s] = shares_i * max(0, basis_i - price_i,s)     loss on lot i at the harvest date
    L_s(x)  = sum_i x_i * l[i, s]                         loss realised by the plan x in [0, 1]^n
    G_s     = realised gains YTD + dollar return of the taxable part of P over the horizon
    K       = tax_rate * E[G]    ("tax" target: losses equal the tax on the expected gains)
            | E[G]               ("offset" target: losses large enough to cancel that tax)

A plan is a set of *conditional* sell orders: on the harvest date, sell fraction x_i of lot i
if it is below its basis, and buy a wash-sale-safe replacement with the proceeds.

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
    target_mode: str = "tax"  # "tax" | "offset"
    realized_gains: float = 0.0  # gains already realised this tax year
    target_override: float | None = None
    tracking_penalty: float = 5.0  # cost per $ sold per unit of (1 - corr) to the replacement
    n_scenarios: int = 10_000
    # extra models the plan must also satisfy (distributionally robust); name -> model
    ambiguity: dict[str, ReturnModel] = field(default_factory=dict)
    seed: int = 7

    @property
    def harvest_on(self) -> date:
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
    taxable = np.array([lot.taxable for lot in p.lots])
    prices = price0[:, None] * np.exp(R[:, idx].T)  # (n_lots, N)
    raw = shares[:, None] * np.clip(basis[:, None] - prices, 0, None)
    pnl_lot = shares[:, None] * (prices - price0[:, None])
    if eligible is None:
        eligible = np.ones(len(p.lots), bool)
    return Scenarios(
        losses=raw * eligible[:, None],
        raw_losses=raw,
        gains=problem.realized_gains + (pnl_lot * taxable[:, None]).sum(0),
        port_pnl=pnl_lot.sum(0),
    )


def target_from(problem: HarvestProblem, sc: Scenarios) -> float:
    if problem.target_override is not None:
        return problem.target_override
    eg = max(sc.gains.mean(), 0.0)
    return problem.tax_rate * eg if problem.target_mode == "tax" else eg


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
            return x_all, {"status": "infeasible: E[L] of every eligible lot < K; using all"}
        x, res = _solve_mean(Lms[0], K, c, ub)
        return x, {"status": res.message}
    if best_cov < alpha:
        return x_all, {"status": f"infeasible: harvesting everything eligible reaches only "
                                 f"P(L>=K)={best_cov:.1%} < {alpha:.0%}; using all"}
    if method == "cvar":
        x, res = _solve_cvar(Lms, K, alpha, c, ub)
        if x is None:
            return x_all, {"status": f"CVaR constraint infeasible at {alpha:.0%} (stricter than "
                                     f"the chance constraint); using all"}
        return x, {"status": res.message}
    if method == "milp":
        rng = rng or np.random.default_rng(0)
        per = max(milp_scenarios // len(Lms), 200)
        subs = [L if L.shape[1] <= per else L[:, rng.choice(L.shape[1], per, replace=False)]
                for L in Lms]
        x, res = _solve_milp(subs, K, alpha, c, ub)
        if x is None:
            return x_all, {"status": f"milp failed ({res.message}); using all"}
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
            return x_all, {"status": "CVaR infeasible at every level; using all"}
        hi, x_hi, cov_hi = lo_f, x_f, cov_f
    if cov_hi < alpha:  # even the tightest feasible CVaR plan misses; fall back to all
        return x_all, {"status": "calibration failed; using all", "solves": solves}
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


# ----------------------------------------------------------------------------- result
@dataclass
class HarvestPlan:
    problem: HarvestProblem
    x: np.ndarray
    status: list[LotStatus]
    replacements: dict[str, Replacement]
    target: float
    losses: np.ndarray  # (N,) in-sample L_s(x)
    gains: np.ndarray
    port_pnl: np.ndarray
    lot_losses: np.ndarray  # (n_lots, N) eligible
    tracking_error: float  # $ 1-sd over the 31-day replacement window
    info: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def confidence(self) -> float:
        return float(np.mean(self.losses >= self.target * (1 - 1e-9)))

    @property
    def expected_loss(self) -> float:
        return float(self.losses.mean())

    @property
    def expected_tax_saved(self) -> float:
        """This year's saving: tax(G) - tax(G - L); losses beyond G carry forward, not counted."""
        G, t = self.gains, self.problem.tax_rate
        return float(np.mean(t * (np.clip(G, 0, None) - np.clip(G - self.losses, 0, None))))

    @property
    def subportfolio_value(self) -> float:
        return float(sum(x * lot.value for x, lot in zip(self.x, self.problem.portfolio.lots)))

    def trades(self) -> pd.DataFrame:
        p = self.problem.portfolio
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
                "sell_frac": round(float(self.x[i]), 4),
                "sell_shares": math.floor(self.x[i] * lot.shares * 1e4) / 1e4,
                "E[loss]": float(self.x[i] * self.lot_losses[i].mean()),
                "P(in loss)": float(np.mean(self.lot_losses[i] > 0)) if st.eligible else np.nan,
                "replace_with": rep.buy if (rep and self.x[i] > 1e-6) else "",
                "corr": rep.corr if (rep and self.x[i] > 1e-6) else np.nan,
                "buy_back_from": rep.buy_back_from if (rep and self.x[i] > 1e-6) else None,
                "why_not": "; ".join(st.reasons),
            })
        return pd.DataFrame(rows)

    def summary(self) -> dict:
        q = np.quantile(self.losses, [0.05, 0.5, 0.95])
        return {
            "jurisdiction": self.problem.rules.code,
            "harvest_on": self.problem.harvest_on,
            "tax_rate": self.problem.tax_rate,
            "target_mode": self.problem.target_mode,
            "E[gain base]": float(self.gains.mean()),
            "target K": self.target,
            "confidence (target)": self.problem.confidence,
            "P(L >= K) in-sample": self.confidence,
            "E[L]": self.expected_loss,
            "L 5/50/95%": tuple(float(v) for v in q),
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
    p, uni = problem.portfolio, problem.universe
    status = screen(p, uni, problem.harvest_on, problem.rules)
    eligible = np.array([s.eligible for s in status])
    sc = simulate(problem, eligible=eligible)
    K = target_from(problem, sc)

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
    x, info = solve_x(Lms, K, problem.confidence, c, ub, method,
                      rng=np.random.default_rng(problem.seed + 1))
    if problem.ambiguity:
        info["worst-case P(L>=K) over ambiguity set"] = coverage(Lms, x, K)
    x = np.where(x > 1e-7, np.minimum(x, 1.0), 0.0)

    harvested_groups = {uni.group(lot.ticker) for xi, lot in zip(x, p.lots) if xi > 0}
    sold = sorted({lot.ticker for xi, lot in zip(x, p.lots) if xi > 0})
    reps = pick_replacements(sold, uni, cov_lookup, problem.harvest_on, problem.rules,
                             harvested_groups)
    plan = HarvestPlan(
        problem=problem, x=x, status=status, replacements=reps, target=K,
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
    return {"confidence": float(np.mean(L >= plan.target * (1 - 1e-9))),
            "E[L]": float(L.mean()), "losses": L}
