"""The sample portfolio under US rules (full report) and under Swiss rules (for contrast)."""

import dataclasses
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taxharvest import report
from taxharvest.engine import HarvestProblem, optimise
from taxharvest.model import Universe
from taxharvest.portfolio import Portfolio
from taxharvest.washsale import CH, US

AS_OF = date(2026, 9, 28)
REALIZED_GAINS = 18_000


def problem(rules, **kw):
    p = Portfolio.from_csv(ROOT / "data/sample_portfolio.csv", AS_OF,
                           ROOT / "data/sample_portfolio_planned.csv")
    uni = Universe.default()
    kw.setdefault("tax_rate", rules.default_tax_rate)
    return HarvestProblem(p, uni, uni.factor_model(p.tickers), rules, confidence=0.90,
                          horizon_days=40, realized_gains=REALIZED_GAINS, **kw)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    print("=== Sample portfolio, US taxpayer, $1,200 tax-savings goal")
    report.run(problem(US, tax_savings_goal=1_200), ROOT / "figures/sample",
               "Sample portfolio, US taxpayer",
               quick=quick)
    print("\n=== Same portfolio, full tax-bill goal")
    print(report.describe(optimise(problem(US))))
    print("\n=== Same portfolio, Swiss resident (amounts in USD)")
    ch_usd = dataclasses.replace(CH, currency="USD")
    print(report.describe(optimise(problem(ch_usd))))
