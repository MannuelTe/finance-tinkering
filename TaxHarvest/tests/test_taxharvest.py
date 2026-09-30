from datetime import date

import numpy as np
import pandas as pd
import pytest

from taxharvest.engine import HarvestProblem, coverage, evaluate, optimise, simulate, solve_x
from taxharvest.model import Universe, fit_gmm, fit_regime_model
from taxharvest.portfolio import Portfolio
from taxharvest.robustness import frontier
from taxharvest.washsale import CA, CH, US, pick_replacements, screen

AS_OF = date(2026, 9, 24)


def _problem(book, rules=US, **kw):
    uni = Universe.default()
    p = Portfolio.from_text(book, AS_OF)
    kw.setdefault("tax_rate", rules.default_tax_rate)
    kw.setdefault("n_scenarios", 3000)
    return HarvestProblem(p, uni, uni.factor_model(p.tickers), rules, **kw)


# ----------------------------------------------------------------------------- parsing
def test_parse_text_with_buys_comments_and_drip():
    p = Portfolio.from_text("""
        VOO 10 600 2025-01-02 550 taxable   # comment
        IVV, 5, 500, 2024-01-01, 575, ira, yes
        buy SPY 2026-10-01 spouse
    """, AS_OF)
    assert [lot.ticker for lot in p.lots] == ["VOO", "IVV"]
    assert p.lots[1].drip and not p.lots[1].taxable
    assert p.planned_buys[0].ticker == "SPY"
    assert p.lots[0].unrealized == pytest.approx(-500)


# ----------------------------------------------------------------------------- rules
def test_screen_blocks_related_account_purchase_drip_and_shelter():
    uni = Universe.default()
    p = Portfolio.from_text("""
        VOO 10 600 2025-01-02 550 taxable
        VTI 10 300 2025-01-02 280 taxable
        XEF 10 40 2025-01-02 35 taxable
        VEA 10 60 2025-01-02 50 taxable
        IEFA 1 80 2024-01-02 70 ira yes
        BND 10 80 2025-01-02 70 ira
        buy IVV 2026-10-20 ira
    """, AS_OF)
    st = screen(p, uni, date(2026, 11, 1), US)
    assert not st[0].eligible and "planned buy of IVV" in st[0].reasons[0]  # same S&P 500 index
    assert st[1].eligible  # VTI tracks a different index
    assert not st[2].eligible and "DRIP" in st[2].reasons[0]  # XEF and IEFA: same MSCI index
    assert st[3].eligible  # VEA tracks FTSE, not MSCI: the IEFA DRIP does not touch it
    assert not st[5].eligible and "sheltered" in st[5].reasons[0]


def test_recent_purchase_blocks_and_reports_clear_date():
    uni = Universe.default()
    p = Portfolio.from_text("""
        ZCN 100 40 2025-01-02 35 taxable
        XIC 10 36 2026-09-20 35 spouse
    """, AS_OF)
    st = screen(p, uni, AS_OF, CA)
    assert not st[0].eligible
    assert st[0].clear_from == date(2026, 10, 21)
    assert screen(p, uni, date(2026, 10, 21), CA)[0].eligible


def test_replacement_leaves_group_and_avoids_harvested_groups():
    uni = Universe.default()
    cov = lambda ts: uni.factor_model(ts).cov
    reps = pick_replacements(["VOO", "VTI"], uni, cov, AS_OF, US, {"SP500", "US_TOTAL_CRSP"})
    for r in reps.values():
        assert uni.group(r.buy) not in {"SP500", "US_TOTAL_CRSP"}
        assert r.corr > 0.95
        assert r.buy_back_from == date(2026, 10, 25)


# ----------------------------------------------------------------------------- optimiser
def _toy(N=4000, seed=0):
    rng = np.random.default_rng(seed)
    Lm = np.clip(rng.normal([[3], [2], [1.5]], 1.0, size=(3, N)), 0, None)
    return Lm, np.array([1.0, 0.8, 0.5]), np.ones(3)


@pytest.mark.parametrize("alpha", [0.7, 0.9])
def test_calibrated_hits_confidence_and_beats_cvar_on_cost(alpha):
    Lm, c, ub = _toy()
    x_cal, _ = solve_x(Lm, 3.0, alpha, c, ub, "calibrated")
    x_cvar, _ = solve_x(Lm, 3.0, alpha, c, ub, "cvar")
    assert coverage(Lm, x_cal, 3.0) >= alpha
    assert coverage(Lm, x_cal, 3.0) < alpha + 0.01
    assert c @ x_cal <= c @ x_cvar + 1e-9


def test_milp_is_exact_in_sample():
    Lm, c, ub = _toy(N=400)
    x, _ = solve_x(Lm, 3.0, 0.85, c, ub, "milp")
    assert coverage(Lm, x, 3.0) >= 0.85


def test_mean_method_matches_target():
    Lm, c, ub = _toy()
    x, _ = solve_x(Lm, 3.0, 0.9, c, ub, "mean")
    assert (x @ Lm).mean() == pytest.approx(3.0, rel=1e-6)


def test_infeasible_and_no_target():
    Lm, c, ub = _toy()
    x, info = solve_x(Lm, 100.0, 0.9, c, ub, "calibrated")
    assert np.all(x == 0) and info["status"].startswith("infeasible")
    x, info = solve_x(Lm, -1.0, 0.9, c, ub, "calibrated")
    assert np.all(x == 0)


def test_end_to_end_plan_respects_screen_and_holds_out_of_sample():
    pr = _problem("""
        VTI 120 318 2025-11-20 292 taxable
        VEA 400 58 2025-07-01 53 taxable
        PFE 500 30 2025-01-10 25 taxable
        DIS 200 118 2025-03-12 96 taxable
        VOO 60 612 2025-12-10 575 taxable
        AAPL 50 190 2023-06-01 228 taxable
        buy IVV 2026-11-01 ira
    """, realized_gains=15_000, tax_savings_goal=1_000,
        confidence=0.9, horizon_days=40)
    plan = optimise(pr)
    df = plan.trades()
    assert df.loc[df.ticker == "VOO", "max_sell_frac"].item() == 0  # blocked by IRA buy
    assert plan.confidence == pytest.approx(0.9, abs=0.01)
    oos = evaluate(plan, 50_000, np.random.default_rng(99))["confidence"]
    assert oos > 0.85
    assert plan.target == 1_000
    assert plan.loss_target == pytest.approx(1_000 / pr.tax_rate)
    assert np.allclose(plan.executed_lot_losses().sum(0), plan.realized_losses)
    assert np.all(plan.realized_losses <= plan.loss_target + 1e-8)
    assert plan.expected_unused_capacity > 0
    assert 0 < plan.expected_market_sold <= plan.subportfolio_value
    assert np.all(plan.tax_savings <= plan.target + 1e-8)
    assert np.all(simulate(pr, n=100).gains == 15_000)  # paper P&L is not taxable gains
    prices = {lot.ticker: lot.cost_basis * 0.5 for lot in pr.portfolio.lots}
    orders = plan.execute(prices)
    assert orders.realized_loss.sum() <= plan.loss_target + 1e-8
    assert orders.tax_saved.sum() == pytest.approx(plan.target, abs=0.01)
    assert orders.attrs["goal_met"]
    assert all(orders.sell_shares > 0)
    for t, r in plan.replacements.items():
        assert pr.universe.group(r.buy) != pr.universe.group(t)


def test_unattainable_tax_goal_is_reported_and_reduced():
    pr = _problem("VTI 100 318 2025-11-20 292 taxable", realized_gains=1_000,
                  tax_savings_goal=500)
    plan = optimise(pr)
    assert plan.requested_target == 500
    assert plan.target <= pr.tax_rate * pr.realized_gains
    assert plan.target < plan.requested_target
    assert plan.confidence >= pr.confidence
    assert "infeasible" in plan.info["status"]
    assert np.all(plan.realized_losses <= plan.loss_target + 1e-8)
    rows, comparable_plans = frontier(pr, alphas=(0.9,), n_in=500)
    assert rows[0]["status"] == "requested goal infeasible"
    assert rows[0]["sub-portfolio value"] is None
    assert comparable_plans == []


def test_switzerland_harvests_nothing():
    pr = _problem("""
        VTI 120 318 2025-11-20 292 taxable
        PFE 500 30 2025-01-10 25 taxable yes
        VOO 10 500 2024-01-01 575 saeule3a
    """, rules=CH, realized_gains=15_000)
    plan = optimise(pr)
    assert pr.tax_rate == 0
    assert plan.target == 0 and not plan.x.any()
    assert "untaxed" in plan.info["status"]
    assert plan.status[1].eligible  # no repurchase rule, so DRIP is irrelevant
    assert not plan.status[2].eligible  # pillar 3a is sheltered


# ----------------------------------------------------------------------------- learning
def test_gmm_recovers_two_regimes():
    rng = np.random.default_rng(0)
    calm = rng.normal(0.001, 0.01, size=(3000, 2))
    crash = rng.normal(-0.004, 0.04, size=(600, 2))
    X = np.vstack([calm, crash])
    fit = fit_gmm(X, 2, rng)
    vols = sorted(np.sqrt(np.diag(c)).mean() for c in fit.covs)
    assert vols[0] == pytest.approx(0.01, rel=0.15)
    assert vols[1] == pytest.approx(0.04, rel=0.15)


def test_regime_model_learns_persistence_and_picks_k_by_bic():
    rng = np.random.default_rng(1)
    states, s = [], 0
    for _ in range(3000):
        states.append(s)
        s = s if rng.random() < (0.98 if s == 0 else 0.9) else 1 - s
    states = np.array(states)
    X = np.where(states[:, None] == 0, rng.normal(0, 0.01, (3000, 2)),
                 rng.normal(-0.003, 0.035, (3000, 2)))
    model, _ = fit_regime_model(pd.DataFrame(X, columns=["A", "B"]), k_max=3, seed=1)
    assert len(model.weights) == 2
    assert np.diag(model.transition).min() > 0.8


# ----------------------------------------------------------------------------- daily
def test_allocate_losses_fills_cheapest_first_and_stops_at_target():
    from taxharvest.engine import allocate_losses
    capacity = np.array([100.0, 300.0, 200.0])
    cost = np.array([500.0, 600.0, 100.0])  # per $ of loss: 5, 2, 0.5
    out = allocate_losses(capacity, cost, 350.0)[:, 0]
    assert out == pytest.approx([0.0, 150.0, 200.0])


def test_daily_review_done_hold_and_deadline_sale():
    from taxharvest import daily
    book = """
        VEA 200 60 2025-01-02 50 taxable
        XOM 100 120 2025-01-02 100 taxable
    """
    pr = _problem(book)
    args = (pr.portfolio, pr.universe, pr.model, US)
    kw = {"realized_gains": 10_000, "tax_savings_goal": 0.238 * 1500, "n_scenarios": 2000,
          "size_pool": False}
    done = daily.review(*args, harvested_loss=1500, deadline=date(2026, 12, 31), **kw)
    assert done.action == "done" and done.progress == pytest.approx(1.0)
    hold = daily.review(*args, deadline=date(2026, 10, 8), **kw)
    assert hold.action == "hold" and hold.wait_confidence >= 0.9
    assert hold.cover == pytest.approx(4000 / 1500)
    last = daily.review(*args, deadline=AS_OF, **kw)
    assert last.action == "sell" and last.days_left == 0
    assert last.orders.realized_loss.sum() == pytest.approx(1500, abs=0.01)
    assert last.orders.ticker.iloc[0] == "VEA"  # replacement tracks it better than XOM's


def test_daily_trigger_beats_one_shot_plan_in_backtest():
    from taxharvest import daily
    pr = _problem("""
        VEA 200 60 2025-01-02 50 taxable
        XOM 100 120 2025-01-02 100 taxable
        NKE 100 90 2025-01-02 80 taxable
    """, realized_gains=20_000, tax_savings_goal=0.238 * 3500, horizon_days=20)
    plan = optimise(pr)
    one = daily.backtest(pr, {"one-shot": -1}, n_paths=300, n_inner=400, pool=plan.x)
    rules = daily.backtest(pr, {"now": 1.01, "daily": 0.9, "weekly": (0.9, 5)},
                           n_paths=300, n_inner=400)
    assert rules["now"]["P(goal met)"] == 1.0  # $6k of loss available today
    assert rules["daily"]["P(goal met)"] > one["one-shot"]["P(goal met)"]
    assert rules["weekly"]["P(goal met)"] > one["one-shot"]["P(goal met)"]
    days = rules["weekly"]["first_sale_day"]
    assert np.all((days % 5 == 0) | (days == 20))  # sales only on review days or the deadline
