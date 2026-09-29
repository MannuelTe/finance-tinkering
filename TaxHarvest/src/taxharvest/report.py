"""Optimise, test and draw one problem into an output folder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import plots, robustness
from .engine import HarvestPlan, HarvestProblem, optimise


def describe(plan: HarvestPlan) -> str:
    s = plan.summary()
    cur = plan.problem.rules.symbol
    lo, med, hi = s["realized loss 5/50/95%"]
    lines = [
        f"Jurisdiction      {plan.problem.rules.name} ({plan.problem.rules.rule})",
        f"Harvest date      {s['harvest_on']}  ({plan.problem.horizon_days} trading days)",
        f"Realized gains    {cur}{s['realized gain base']:,.0f}",
        f"Tax-saving goal   {cur}{s['tax saving goal']:,.0f}  (rate {s['tax_rate']:.2%})",
        f"Loss needed       {cur}{s['loss needed for goal']:,.0f}",
        (f"P(save >= goal)   {s['P(tax saved >= goal) in-sample']:.1%}  "
         f"(required {s['confidence (target)']:.0%})"),
        (f"E[loss realized] {cur}{s['E[loss realized]']:,.0f}   5/50/95%: {cur}{lo:,.0f} / "
         f"{cur}{med:,.0f} / {cur}{hi:,.0f}"),
        f"E[tax saved]      {cur}{s['E[tax saved]']:,.0f}",
        f"E[unused capacity] {cur}{s['E[unused loss capacity]']:,.0f}",
        f"E[market sold]    {cur}{s['E[market sold at current prices]']:,.0f}",
        (f"Candidate pool    {cur}{s['sub-portfolio value']:,.0f}  "
         f"({s['sub-portfolio share of P']:.1%} of P)"),
        (f"Full-pool tracking {cur}{s['tracking error 31d ($, 1sd)']:,.0f} "
         f"(1 sd over the 31-day replacement window)"),
        f"Solver            {s['status']}  [{s['seconds']}s]",
    ]
    if s["requested tax saving goal"] > s["tax saving goal"] + 1e-9:
        lines.insert(4, f"Requested goal    {cur}{s['requested tax saving goal']:,.0f}; "
                        f"reliable maximum {cur}{s['max reliable tax saving']:,.0f}")
    worst = plan.info.get("worst-case P(tax saved >= goal) over ambiguity set")
    if worst is not None:
        lines.insert(5, f"  worst case      {worst:.1%} over the ambiguity set "
                        f"({', '.join(plan.problem.ambiguity)})")
    return "\n".join(lines)


def trade_list(plan: HarvestPlan) -> str:
    df = plan.trades()
    cur = plan.problem.rules.symbol
    out = []
    sel = df[df.max_sell_frac > 0]
    if len(sel):
        out.append(f"Maximum conditional sales for {plan.problem.harvest_on}: sell only below "
                   f"basis, rank available lots by replacement-adjusted cost per dollar "
                   f"of loss, and stop once {cur}{plan.target:,.0f} tax saving is reached "
                   f"({cur}{plan.loss_target:,.0f} of loss). The last sale may be partial.")
        for _, r in sel.iterrows():
            out.append(
                f"  SELL UP TO {r.max_sell_shares:g} {r.ticker} "
                f"({r.account}, lot of {r.acquired}) "
                f"-> BUY {r.replace_with} (corr {r["corr"]:.2f}); E[loss] {cur}{r['E[loss]']:,.0f}, "
                f"P(in loss) {r['P(in loss)']:.0%}; do not rebuy {r.ticker} or its index twins "
                f"in ANY account before {r.buy_back_from}"
            )
    blocked = df[~df.eligible & (df.unrealized < 0)]
    if len(blocked):
        out.append("Losing lots the screen blocked:")
        for _, r in blocked.iterrows():
            out.append(f"  {r.ticker} ({r.account}, {cur}{r.unrealized:,.0f}): {r.why_not}")
    return "\n".join(out)


def run(problem: HarvestProblem, out: Path, title: str = "", method="calibrated",
        robust=True, quick=False, animate=True, log=print, extra_models=None,
        compare_robust=True) -> HarvestPlan:
    out.mkdir(parents=True, exist_ok=True)
    plan = optimise(problem, method)
    log(describe(plan))
    log(trade_list(plan))
    plan.trades().to_csv(out / "trades.csv", index=False)
    cur = problem.rules.symbol

    plots.plan_overview(plan, out / "plan.png", title)
    plots.tax_impact(plan, out / "tax_impact.png")
    log("  frontier over confidence levels")
    rows, fplans = robustness.frontier(problem, alphas=(0.5, 0.7, 0.8, 0.9, 0.95) if quick else
                                       (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.975, 0.99))
    plots.frontier(rows, out / "frontier.png", cur, problem.confidence)
    summary = {k: (str(v) if not isinstance(v, (int, float, tuple)) else v)
               for k, v in plan.summary().items()}
    summary["frontier"] = rows
    if robust and np.any(plan.x):
        rob = robustness.run_all(plan, quick=quick, log=log, extra_models=extra_models)
        plots.robustness(rob, out / "robustness.png", problem.confidence)
        summary["robustness"] = {
            "seeds_mean": {k: float(np.mean(v)) for k, v in rob["seeds"].items()},
            "convergence": rob["convergence"],
            "param_median": float(np.median(rob["param"])),
            "param_p05": float(np.quantile(rob["param"], 0.05)),
            "misspec": rob["misspec"],
        }
        if compare_robust:
            log("  distributionally robust plan (ambiguity set) vs nominal")
            amb = robustness.ambiguity_set(problem.model)
            rplan = optimise(robustness._with(problem, ambiguity=amb, n_scenarios=4000), method)
            log(describe(rplan))
            rmis = robustness.misspecification(rplan, n_out=50_000 if quick else 200_000,
                                               extra=extra_models)
            comparable = abs(rplan.target - plan.target) < 1e-9
            if comparable:
                plots.nominal_vs_robust(plan, rplan, rob["misspec"], rmis, list(amb),
                                        out / "robust_vs_nominal.png")
            else:
                (out / "robust_vs_nominal.png").unlink(missing_ok=True)
                log("  robust comparison chart omitted: the robust plan has a lower "
                    "tax-saving goal")
            rplan.trades().to_csv(out / "trades_robust.csv", index=False)
            summary["robust_plan"] = {
                "ambiguity_set": list(amb),
                "tax saving goal": rplan.target,
                "same goal as nominal": comparable,
                "status": rplan.info["status"],
                "sub-portfolio value": rplan.subportfolio_value,
                "E[loss realized]": rplan.expected_loss,
                "misspec": rmis,
            }
            if not comparable:
                summary["robust_plan"]["requested tax saving goal"] = rplan.requested_target
                summary["robust_plan"]["max reliable tax saving"] = rplan.info[
                    "max_reliable_tax_saving"]
    elif not np.any(plan.x):
        for name in ("robustness.png", "robust_vs_nominal.png", "trades_robust.csv"):
            (out / name).unlink(missing_ok=True)
    if animate and np.any(plan.x):
        log("  animations")
        plots.animate_loss_fan(plan, out / "loss_fan.gif")
        plots.animate_mc_convergence(plan, out / "mc_convergence.gif")
        if fplans:
            plots.animate_frontier(fplans, out / "frontier_sweep.gif")
        else:
            (out / "frontier_sweep.gif").unlink(missing_ok=True)
    elif not np.any(plan.x):
        for name in ("loss_fan.gif", "mc_convergence.gif", "frontier_sweep.gif"):
            (out / name).unlink(missing_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return plan
