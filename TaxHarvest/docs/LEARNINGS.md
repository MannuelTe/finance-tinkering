# Learnings

What this project taught me, in rough order of how much it changed the design.

## About the problem

1. **"Expected losses equal the target" is a coin flip.** Solving `E[L] = K` exactly gave
   P(L ≥ K) of 46–52% out of sample in every example. Planning a harvest needs a *confidence*
   level, which makes it a chance-constrained problem, not a mean-matching one.

2. **The wash-sale rules cost more than the optimiser saves.** In the US example the three
   blocked lots (an IRA contribution, a spouse's purchase and a forgotten DRIP) hold $12.1k of
   losses, more than the plan's whole expected harvest. Both regimes look *across accounts*
   (Rev. Rul. 2008-5 for IRAs, "affiliated person" in Canada), so a screen that only looks at
   the taxable account is wrong in exactly the cases that matter. Operationally the
   biggest lever is to turn off DRIPs and pause contributions to same-index funds 31 days
   ahead.

3. **Fat tails don't hurt a harvest; rallies do.** Student-t and a persistent crisis regime
   both left confidence at or *above* target, because crashes create losses. What breaks
   the plan is anything that lets losing lots recover before the harvest date: +50% vol
   (80–86%) or a strong rally (79–82% on 40-day horizons). This is the reverse of the intuition from
   risk management.

4. **Cheap losses come with bad replacements.** The optimiser likes single stocks deep
   underwater (PFE, DIS, BCE), because their losses are nearly certain. Their best
   non-identical replacement is a sector ETF with ρ ≈ 0.4–0.7, while index ETFs swap into a
   sister index at ρ ≈ 1.0. Harvest size and tracking error pull in opposite directions, and
   the tracking-penalty weight λ is a real choice, not a detail.

5. **The literal target is small.** Losses equal to `τ · E[G]` (the tax itself) are only about
   a quarter of the losses needed to cancel the tax (`E[G]`). Both are supported
   (`--target tax|offset`), and the choice changes feasibility more than any modelling
   decision does.

## About the optimisation

6. **CVaR is the wrong tool when you need a specific confidence.** The CVaR LP is the standard
   convex stand-in for a chance constraint. Here it over-covered (94–96% for a 90% target),
   sold almost twice as much in the Canada case, and in two examples was *infeasible* where
   the chance constraint was satisfiable. The fix that worked: search over the CVaR level α′
   for the smallest one whose LP solution still meets the real chance constraint
   in-sample. That lands exactly on α and stays convex.

7. **Exact in-sample chance constraints do generalise here.** With ~15 decision variables and
   thousands of scenarios, the sample-average approximation barely overfits. Out-of-sample
   confidence was within about 1 point of target from N = 1,000, and the MILP
   (exact on its subsample) did no better than the calibrated LP.

8. **Estimation error, not Monte Carlo error, is the real uncertainty.** Monte Carlo noise at
   N = 8,000 is ±0.5 points. Five years of data leaves enough drift uncertainty to push a
   40-day plan down to 83–84% in a bad draw. If you want a guarantee, make the plan robust
   to the *model*. More scenarios won't help. The ambiguity-set version recovered 5–9 points
   of the stress-case losses, and it cost 15–90% more harvested value.

## About the learned model

9. **Counting regime transitions from mixture labels badly underestimates persistence.**
   My first version fitted a GMM and counted transitions between hard labels. It estimated
   P(stay in crisis) = 0.58 when the truth was 0.90: calm-looking crisis days get mislabelled
   and break the runs. Baum–Welch initialised from the GMM recovered 0.939 vs 0.93. Over a
   multi-week horizon persistence is what matters, so the shortcut was not acceptable.

10. **BIC was enough.** On 2,500 days it picked the true k = 2 without any tuning.

## About the engineering

11. **HiGHS: IPM, not simplex, for scenario LPs, and always set a time limit.** Dual simplex
    took 28 s on a 20k-scenario CVaR LP that IPM solved in 3 s. IPM can stall indefinitely
    near the feasibility boundary, though, and one solve hung the robustness run for 10+
    minutes. The fix was a time limit with a dual-simplex retry.

12. **Bisection is wasteful when the function is smooth.** Coverage is smooth and monotone in
    the CVaR level, so regula falsi (Illinois variant) needs 3–5 LP solves where bisection
    needed 9–15. That cut the robust plan from over 10 minutes to about 40 s.

13. **macOS + synced folders + Python 3.13 break editable installs.** Something sets the
    `hidden` flag on the venv's `.pth` files, and Python 3.13 skips hidden `.pth` files.
    `scripts/th.py` inserts `src/` itself.

## What I would do next

* A re-planning policy instead of one harvest date: harvest whatever is in the money each
  week, keeping the remaining target and the 30-day windows as state.
* US short-term/long-term netting and a proper after-tax objective (tax alpha minus the
  tracking-error cost).
* A learned replacement universe: pick replacements from actual return histories, with
  an explicit "substantially identical" margin, not a hand-curated table.
