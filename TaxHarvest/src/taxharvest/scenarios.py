"""Worked example portfolios. Prices and bases are made up for illustration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from .engine import HarvestProblem
from .model import RegimeModel, ReturnModel, Universe, fit_regime_model
from .portfolio import Portfolio
from .washsale import CA, US

AS_OF = date(2026, 9, 24)

US_BOOK = """
# ticker shares basis acquired price account drip
VOO   60  612.0 2025-12-10 575.0 taxable
VTI  120  318.0 2025-11-20 292.0 taxable
QQQ   30  540.0 2026-01-15 548.0 taxable
VEA  400   58.0 2025-07-01  53.0 taxable
VWO  300   47.0 2026-03-03  45.5 taxable
BND  200   74.0 2024-05-14  72.5 taxable
AAPL  50  190.0 2023-06-01 228.0 taxable
NVDA  40   95.0 2023-02-01 172.0 taxable
INTC 500   34.0 2024-03-01  22.0 taxable yes
NKE  150   98.0 2024-08-01  72.0 taxable
PFE  500   30.0 2025-01-10  25.0 taxable
DIS  200  118.0 2025-03-12  96.0 taxable
XOM  100  125.0 2025-04-02 112.0 taxable
JPM   60  205.0 2024-10-01 290.0 taxable
IVV  100  500.0 2024-06-01 575.0 ira
buy IVV 2026-11-01 ira          # monthly IRA contribution -> blocks VOO (same index)
buy NKE 2026-11-10 spouse       # spouse's purchase -> blocks NKE
"""

CA_BOOK = """
XIC   500  40.10 2025-10-06 38.20 taxable
VFV   200 150.00 2026-02-11 141.00 taxable
XEF   600  40.00 2025-06-02 37.50 taxable
ZAG   800  14.60 2023-05-01 13.90 taxable
SHOP   60 160.00 2025-11-03 142.00 taxable
ENB   300  58.00 2024-01-15 62.00 taxable
RY    150 150.00 2023-03-01 185.00 taxable
BCE   400  52.00 2024-02-01 33.00 taxable
CNQ   200  46.00 2025-05-20 43.50 taxable
TD    200  82.00 2025-02-10 90.00 taxable
VUN   300  95.00 2024-09-01 118.00 rrsp
XUS   150  48.00 2025-01-01 52.00 tfsa yes
buy ZCN 2026-11-15 spouse_taxable   # spouse (affiliated person) buys same index as XIC
"""

YEAR_END_BOOK = """
VTI  150 310.0 2025-11-20 288.0 taxable
VTI   20 291.0 2026-12-01 288.0 taxable     # bought 9 days ago -> blocks the old VTI lot
VEA  500  57.0 2025-07-01  52.5 taxable
NKE  200  99.0 2024-08-01  70.0 taxable
PFE  500  31.0 2025-01-10  24.5 taxable
AAPL 100 150.0 2022-06-01 230.0 taxable
"""


@dataclass
class Example:
    name: str
    title: str
    problem: HarvestProblem
    blurb: str
    true_model: ReturnModel | None = None  # for the learned-regime example
    history: pd.DataFrame | None = None
    fits: list | None = None


def _problem(book, as_of, rules, universe, model=None, **kw):
    p = Portfolio.from_text(book, as_of)
    model = model or universe.factor_model(p.tickers)
    return HarvestProblem(p, universe, model, rules, tax_rate=kw.pop("tax_rate",
                          rules.default_tax_rate), **kw)


def us_core() -> Example:
    uni = Universe.default()
    pr = _problem(US_BOOK, AS_OF, US, uni, confidence=0.90, horizon_days=40,
                  realized_gains=15_000, target_mode="tax")
    return Example("us_core", "US taxpayer, harvest in ~8 weeks", pr,
                   "Taxable + IRA + spouse. IRA contribution blocks VOO, spouse blocks NKE, "
                   "DRIP blocks INTC. Target: losses = 23.8% x expected gains, 90% confidence.")


def canada() -> Example:
    uni = Universe.default()
    pr = _problem(CA_BOOK, AS_OF, CA, uni, confidence=0.90, horizon_days=40,
                  realized_gains=20_000, target_mode="tax")
    return Example("canada", "Canadian taxpayer, superficial-loss rule", pr,
                   "Spouse's planned ZCN buy blocks XIC (same index), TFSA DRIP on XUS blocks "
                   "VFV. Tax rate 50% inclusion x 53.53%.")


def _true_regime(uni: Universe, tickers) -> RegimeModel:
    g = uni.factor_model(tickers)
    m = len(tickers)
    eq = np.array([uni.table.at[t, "factor"].endswith("EQ") for t in tickers], float)
    calm_mu = g.mu + 0.0003 * eq
    crisis_mu = g.mu - 0.0025 * eq
    calm_cov = 0.6 * g.cov
    crisis_cov = 3.0 * g.cov + 0.2 * np.outer(np.sqrt(np.diag(g.cov)), np.sqrt(np.diag(g.cov)))
    P = np.array([[0.985, 0.015], [0.07, 0.93]])
    pi = np.array([P[1, 0], P[0, 1]]) / (P[1, 0] + P[0, 1])
    return RegimeModel(pi, np.stack([calm_mu, crisis_mu]),
                       np.stack([calm_cov, crisis_cov + 1e-12 * np.eye(m)]), P, list(tickers))


def learned_regime(days_history=2500, seed=11) -> Example:
    """F_P learned from (synthetic) daily history: Gaussian HMM, k by BIC."""
    uni = Universe.default()
    p = Portfolio.from_text(US_BOOK, AS_OF)
    true = _true_regime(uni, p.tickers)
    rng = np.random.default_rng(seed)
    hist = true.sample_paths(1, days_history, rng)[0]
    daily = np.diff(np.vstack([np.zeros(len(p.tickers)), hist]), axis=0)
    history = pd.DataFrame(daily, columns=p.tickers)
    fitted, fits = fit_regime_model(history, k_max=3, restarts=2, seed=seed)
    pr = HarvestProblem(p, uni, fitted, US, tax_rate=US.default_tax_rate, confidence=0.90,
                        horizon_days=40, realized_gains=15_000, target_mode="tax")
    return Example("learned_regime", "US book, F_P learned from 10y of daily returns", pr,
                   "Gaussian HMM (EM mixture init + Baum-Welch, k by BIC) learned from history. "
                   "Fat, clustered tails vs the Gaussian factor model.", true_model=true,
                   history=history, fits=fits)


def year_end() -> Example:
    uni = Universe.default()
    pr = _problem(YEAR_END_BOOK, date(2026, 12, 10), US, uni, confidence=0.95, horizon_days=5,
                  realized_gains=9_000, target_mode="offset")
    return Example("year_end", "Year-end sprint, 5 trading days, offset all gains", pr,
                   "Short horizon: losses are nearly known. A VTI lot bought 9 days ago "
                   "blocks the old VTI lot. Target: losses = E[gains] (full offset), 95%.")


EXAMPLES = {"us_core": us_core, "canada": canada, "learned_regime": learned_regime,
            "year_end": year_end}
