"""Monte Carlo evidence that a plan's confidence is real and not an artefact of one sample.

Four tests, all measured out of sample on fresh scenarios:

1. seeds        - re-optimise on independent scenario sets; spread of achieved P(L >= K)
2. convergence  - the same as a function of the number of optimisation scenarios N
3. parameters   - hold the plan fixed, redraw the "true" mu and Sigma from their sampling
                  distribution given `est_years` of daily data (Normal / Wishart)
4. misspecified - hold the plan fixed, change the family of F (fat tails, higher vol,
                  a persistent crisis regime, a strong rally)
"""

from __future__ import annotations

import copy

import numpy as np
from scipy.stats import wishart

from .engine import HarvestPlan, HarvestProblem, evaluate, optimise
from .model import TRADING_DAYS, GaussianModel, RegimeModel, StudentTModel


def wilson(p, n, z=1.96):
    p, n = np.asarray(p, float), np.asarray(n, float)
    den = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return c - h, c + h


def _with(problem: HarvestProblem, **kw) -> HarvestProblem:
    p = copy.copy(problem)
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def seed_study(problem, methods=("mean", "cvar", "calibrated", "milp"), n_seeds=10, n_in=5000,
               n_out=100_000, log=print):
    out = {}
    for m in methods:
        vals = []
        for s in range(n_seeds):
            plan = optimise(_with(problem, n_scenarios=n_in, seed=1000 + s), m)
            vals.append(evaluate(plan, n_out, np.random.default_rng(50_000 + s))["confidence"])
        out[m] = vals
        log(f"    seeds[{m}]: mean OOS confidence {np.mean(vals):.3f} (sd {np.std(vals):.3f})")
    return out


def convergence(problem, Ns=(250, 500, 1000, 2000, 4000, 8000), n_seeds=5, n_out=100_000,
                method="calibrated", log=print):
    mean, sd = [], []
    for N in Ns:
        vals = []
        for s in range(n_seeds):
            plan = optimise(_with(problem, n_scenarios=N, seed=2000 + s), method)
            vals.append(evaluate(plan, n_out, np.random.default_rng(60_000 + s))["confidence"])
        mean.append(float(np.mean(vals)))
        sd.append(float(np.std(vals)))
        log(f"    N={N:>6}: {mean[-1]:.3f} ± {sd[-1]:.3f}")
    return {"N": list(Ns), "mean": mean, "sd": sd}


def parameter_uncertainty(plan: HarvestPlan, draws=200, est_years=5, n_out=20_000, seed=3):
    mu, cov = plan.problem.model.daily_moments()
    T = int(est_years * TRADING_DAYS)
    rng = np.random.default_rng(seed)
    W = wishart(df=T, scale=cov / T)
    vals = []
    for _ in range(draws):
        cov_t = W.rvs(random_state=rng)
        mu_t = rng.multivariate_normal(mu, cov / T)
        m = GaussianModel(mu_t, cov_t, list(plan.problem.model.tickers))
        vals.append(evaluate(plan, n_out, rng, model=m)["confidence"])
    return vals


def misspecification(plan: HarvestPlan, n_out=200_000, seed=4, extra: dict | None = None):
    base = plan.problem.model
    mu, cov = base.daily_moments()
    t = list(base.tickers)
    sd = np.sqrt(np.diag(cov))
    crisis = RegimeModel(
        np.array([0.82, 0.18]),
        np.stack([mu + 0.02 * sd, mu - 0.15 * sd]),
        np.stack([0.6 * cov, 3.0 * cov + 0.2 * np.outer(sd, sd)]),
        np.array([[0.985, 0.015], [0.07, 0.93]]), t)
    models = {
        "optimised model": base,
        "Student-t, df=4": StudentTModel(mu, cov, 4.0, t),
        "volatility +50%": GaussianModel(mu, 2.25 * cov, t),
        "persistent crisis regime": crisis,
        "strong rally (+20%/yr drift)": GaussianModel(mu + 0.20 / TRADING_DAYS, cov, t),
    }
    models.update(extra or {})
    rng = np.random.default_rng(seed)
    out = {}
    for name, m in models.items():
        c = evaluate(plan, n_out, rng, model=m)["confidence"]
        lo, hi = wilson(c, n_out)
        out[name] = {"confidence": c, "ci": (float(lo), float(hi))}
    return out


def ambiguity_set(model) -> dict:
    """Default set of alternative F a robust plan must also satisfy.

    Deliberately milder than the stress tests in ``misspecification`` (vol +30% vs +50%,
    drift +/-10%/yr vs +20%/yr), so that testing the robust plan there is not circular.
    """
    mu, cov = model.daily_moments()
    t = list(model.tickers)
    return {
        "vol +30%": GaussianModel(mu, 1.69 * cov, t),
        "drift +10%/yr": GaussianModel(mu + 0.10 / TRADING_DAYS, cov, t),
        "drift -10%/yr": GaussianModel(mu - 0.10 / TRADING_DAYS, cov, t),
        "Student-t, df=4": StudentTModel(mu, cov, 4.0, t),
    }


def frontier(problem, alphas=(0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.975, 0.99), n_in=5000,
             method="calibrated"):
    rows, plans = [], []
    for a in alphas:
        plan = optimise(_with(problem, confidence=a, n_scenarios=n_in), method)
        plans.append(plan)
        s = plan.summary()
        rows.append({"alpha": a, "K": plan.target, "confidence": plan.confidence,
                     "E[L]": s["E[L]"], "E[tax saved]": s["E[tax saved]"],
                     "sub-portfolio value": s["sub-portfolio value"],
                     "status": s["status"]})
    return rows, plans


def run_all(plan: HarvestPlan, quick=False, log=print, extra_models=None):
    pr = plan.problem
    log("  robustness: re-optimising on independent seeds")
    seeds = seed_study(pr, n_seeds=4 if quick else 10, log=log,
                       methods=("mean", "cvar", "calibrated") if quick else
                       ("mean", "cvar", "calibrated", "milp"))
    log("  robustness: SAA convergence")
    conv = convergence(pr, Ns=(250, 1000, 4000) if quick else (250, 500, 1000, 2000, 4000, 8000),
                       n_seeds=3 if quick else 5, log=log)
    log("  robustness: parameter uncertainty")
    param = parameter_uncertainty(plan, draws=60 if quick else 200)
    log("  robustness: model misspecification")
    mis = misspecification(plan, n_out=50_000 if quick else 200_000, extra=extra_models)
    return {"seeds": seeds, "n_seeds": len(next(iter(seeds.values()))), "convergence": conv,
            "param": param, "est_years": 5, "misspec": mis}
