"""Pro forma deal arithmetic for the two candidate acquisitions, Swiss version.

Aareland Regionalbank (A) can buy Novafin Kreditbank (B) or Banca Alpina (C).
The deal is recomputed under whatever macro scenario is selected, so the
capital position reflects stressed value adjustments rather than the base case.

Two Swiss features change the capital arithmetic:

*  The CET1 requirement is the management target on total RWA **plus** a
   sectoral buffer on residential mortgage positions. A mortgage-heavy target
   therefore costs more capital than its risk-weighted assets alone imply.
*  New equity attracts the 1% federal issuance duty (Emissionsabgabe), so an
   equity raise has to be grossed up to land on the required amount.

Scope note: this is a run-rate model with synergy phase-in on flat underlying
earnings. Cost synergy assumptions are set below what a single-language market
would support, because a Swiss retail bank runs its documentation, contact
centres and consumer-credit disclosures in three languages.
"""

from dataclasses import dataclass

import banks as bk
from engine import (
    TAX_RATE,
    CET1_MANAGEMENT_TARGET,
    CET1_REGULATORY_MIN,
    SECTORAL_CCYB,
    required_cet1,
)


@dataclass(frozen=True)
class DealTerms:
    target: str
    price: float                     # CHF mm all-cash consideration
    debt_share: float
    debt_rate: float                 # Swiss franc funding, low by intl. standards
    cost_synergy: float              # CHF mm pretax run-rate
    phase: tuple[float, float, float]
    revenue_synergy: float
    integration_cost: float
    day1_provision: float

    @property
    def debt(self) -> float:
        return self.price * self.debt_share

    @property
    def interest(self) -> float:
        return self.debt * self.debt_rate


DEALS = {
    "Novafin Kreditbank (B)": DealTerms(
        target="Novafin Kreditbank (B)",
        price=1_450, debt_share=0.70, debt_rate=0.0215,
        cost_synergy=72, phase=(0.40, 0.80, 1.00),
        revenue_synergy=18, integration_cost=95, day1_provision=55,
    ),
    "Banca Alpina (C)": DealTerms(
        target="Banca Alpina (C)",
        price=880, debt_share=0.50, debt_rate=0.0185,
        cost_synergy=65, phase=(0.50, 0.85, 1.00),
        revenue_synergy=22, integration_cost=55, day1_provision=8,
    ),
}


def goodwill(terms: DealTerms) -> float:
    """Price paid less the net assets actually acquired.

    Note the Swiss wrinkle: statutory accounts may carry undisclosed reserves,
    so the net assets acquired could exceed reported book value. Any such
    reserves found in diligence reduce goodwill and are a price negotiation.
    """
    target_equity = bk.BANK_FACTS[terms.target].equity
    return terms.price - (target_equity - terms.day1_provision)


def gross_up_for_stamp_duty(net_needed: float) -> tuple[float, float]:
    """Size an equity raise so that the proceeds net of issuance duty meet the
    requirement. Returns (gross raise, duty).

    The duty is 1% on the amount above a CHF 1m exemption, so:
        raise - 0.01 * (raise - exemption) = net_needed
    """
    if net_needed <= 0:
        return 0.0, 0.0
    r = bk.STAMP_DUTY_RATE
    e = bk.STAMP_DUTY_EXEMPTION
    gross = (net_needed - r * e) / (1 - r)
    duty = r * max(0.0, gross - e)
    return gross, duty


def pro_forma(terms: DealTerms, summary) -> dict:
    """Combine acquirer and target under the scenario already applied."""
    acq = "Aareland Regionalbank (A)"
    a = summary.loc[acq]
    t = summary.loc[terms.target]

    gw = goodwill(terms)

    va_hit = (a["va_delta"] + t["va_delta"]) * (1 - TAX_RATE)
    cet1 = a["cet1_base"] - gw - va_hit
    rwa = a["rwa_stressed_total"] + t["rwa_stressed_total"]
    mortgage_rwa = a["mortgage_rwa"] + t["mortgage_rwa"]

    ratio_pre = cet1 / rwa
    sectoral = SECTORAL_CCYB * mortgage_rwa
    required = required_cet1(rwa, mortgage_rwa)
    # Effective required ratio once the mortgage buffer is expressed on total RWA.
    required_ratio = required / rwa

    net_needed = max(0.0, required - cet1)
    raise_gross, duty = gross_up_for_stamp_duty(net_needed)

    price_per_share = bk.BANK_FACTS[acq].price
    base_shares = bk.BANK_FACTS[acq].shares_mm
    new_shares = raise_gross / price_per_share if price_per_share else 0.0
    total_shares = base_shares + new_shares

    cet1_post = cet1 + raise_gross - duty
    ratio_post = cet1_post / rwa

    ni_a = a["net_income_stressed"]
    ni_t = t["net_income_stressed"]
    standalone_eps = bk.BANK_FACTS[acq].net_income / base_shares

    years = []
    for i, phase in enumerate(terms.phase, start=1):
        synergy = (terms.cost_synergy * phase
                   + terms.revenue_synergy * min(1.0, phase * 1.25))
        pretax = synergy - terms.interest
        if i == 1:
            pretax -= terms.integration_cost
        combined_ni = ni_a + ni_t + pretax * (1 - TAX_RATE)
        eps = combined_ni / total_shares if total_shares else 0.0
        years.append({
            "year": i,
            "synergy_pretax": synergy,
            "interest": terms.interest,
            "integration": terms.integration_cost if i == 1 else 0.0,
            "net_income": combined_ni,
            "eps": eps,
            "accretion": (eps / standalone_eps - 1) if standalone_eps else 0.0,
        })

    return {
        "target": terms.target,
        "price": terms.price,
        "goodwill": gw,
        "cet1_pre_raise": cet1,
        "rwa": rwa,
        "mortgage_rwa": mortgage_rwa,
        "sectoral_buffer": sectoral,
        "required_cet1": required,
        "required_ratio": required_ratio,
        "ratio_pre_raise": ratio_pre,
        "raise_needed": raise_gross,
        "stamp_duty": duty,
        "new_shares": new_shares,
        "dilution": new_shares / total_shares if total_shares else 0.0,
        "ratio_post_raise": ratio_post,
        "breaches_minimum": ratio_pre < CET1_REGULATORY_MIN,
        "meets_target": cet1 >= required,
        "standalone_eps": standalone_eps,
        "years": years,
        "va_hit": va_hit,
    }


def compare(summary) -> dict[str, dict]:
    """Run both candidate deals under the current scenario."""
    idx = summary.set_index("bank")
    return {name: pro_forma(terms, idx) for name, terms in DEALS.items()}
