"""US wash-sale (IRC s.1091) and Canadian superficial-loss (ITA s.54) screens.

Both rules deny a loss when the same (US: "substantially identical"; Canada: "identical")
property is acquired within 30 days before or after the sale, by the taxpayer or a related
party. We model identity with ``wash_group`` in the asset table: tickers tracking the same
index share a group (VOO/IVV/SPY/VFV/ZSP/XUS are all "SP500"). That is the conservative
reading; the IRS and CRA have never published a list, so a group boundary is a judgement.

What the screen checks, for a harvest (sale) on date H:

1. The lot sits in a taxable account (losses in IRA/RRSP/TFSA are not deductible).
2. No other lot of the same group, in *any* account (taxable, IRA/RRSP/TFSA, spouse), was
   acquired in [H-30, H]. US: Rev. Rul. 2008-5 covers IRA purchases. Canada: an affiliated
   person includes a spouse; CRA also treats the taxpayer's RRSP/TFSA purchases as triggering.
3. No planned purchase of the same group in [H-30, H+30].
4. DRIP is off for every lot of that group (a reinvested dividend is a purchase).
5. The replacement bought with the proceeds is in a *different* group, and no group that is
   being harvested is used as another lot's replacement.
6. The original can be bought back from H+31 on (Canada: the property must not be held at
   the end of day 30, so H+31 is also the first safe day).

Canada has one extra condition that makes it *narrower* (the replacement must still be held
at day 30 for the loss to be superficial); we still block on it because selling the
recently bought lot to dodge the rule is a separate decision the user should make.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from .model import Universe
from .portfolio import Portfolio


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    name: str
    rule: str
    window_before: int = 30
    window_after: int = 30
    currency: str = "USD"
    # default *effective* rate on the loss (what one dollar of harvested loss saves)
    default_tax_rate: float = 0.238
    note: str = ""


US = Jurisdiction(
    "US", "United States", "wash sale (IRC s.1091)", currency="USD", default_tax_rate=0.238,
    note="23.8% = 20% long-term rate + 3.8% NIIT. Short-term gains are taxed at ordinary rates.",
)
CA = Jurisdiction(
    "CA", "Canada", "superficial loss (ITA s.54)", currency="CAD",
    default_tax_rate=0.5 * 0.5353,
    note="26.8% = 50% inclusion x 53.53% top Ontario marginal rate.",
)
JURISDICTIONS = {"US": US, "CA": CA}


@dataclass
class LotStatus:
    index: int
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    clear_from: date | None = None  # earliest harvest date at which purchase blocks lift


def screen(portfolio: Portfolio, universe: Universe, harvest_on: date,
           rules: Jurisdiction) -> list[LotStatus]:
    lo = harvest_on - timedelta(days=rules.window_before)
    hi = harvest_on + timedelta(days=rules.window_after)
    lots = portfolio.lots
    out = []
    for i, lot in enumerate(lots):
        st = LotStatus(i, True)
        g = universe.group(lot.ticker)
        if not lot.taxable:
            st.eligible = False
            st.reasons.append(f"sheltered account ({lot.account}): loss not deductible")
        for j, other in enumerate(lots):
            if j == i or universe.group(other.ticker) != g:
                continue
            if lo <= other.acquired <= harvest_on:
                st.eligible = False
                st.reasons.append(
                    f"{other.ticker} bought {other.acquired} in {other.account} "
                    f"(within {rules.window_before}d before sale)"
                )
                clear = other.acquired + timedelta(days=rules.window_before + 1)
                st.clear_from = max(st.clear_from or clear, clear)
            if other.drip:
                st.eligible = False
                st.reasons.append(f"DRIP on {other.ticker} in {other.account}: switch it off")
        if lot.drip:
            st.eligible = False
            st.reasons.append("DRIP on this lot: switch it off")
        for b in portfolio.planned_buys:
            if b.ticker in universe and universe.group(b.ticker) == g and lo <= b.on <= hi:
                st.eligible = False
                st.reasons.append(f"planned buy of {b.ticker} on {b.on} in {b.account}")
        out.append(st)
    return out


@dataclass
class Replacement:
    sold: str
    buy: str
    corr: float
    buy_back_from: date


def pick_replacements(sold_tickers: list[str], universe: Universe, cov_lookup, harvest_on: date,
                      rules: Jurisdiction, blocked_groups: set[str],
                      candidates: list[str] | None = None) -> dict[str, Replacement]:
    """Most-correlated asset outside the sold group and outside every harvested group.

    ``cov_lookup(tickers) -> covariance`` lets this work for any return model. Same-listing
    candidates win ties within 0.5 correlation points (avoids FX conversion in a CAD account).
    """
    cand_all = candidates or list(universe.table.index)
    out = {}
    for t in sold_tickers:
        g = universe.group(t)
        cands = [c for c in cand_all if universe.group(c) != g
                 and universe.group(c) not in blocked_groups]
        if not cands:
            continue
        cov = cov_lookup([t, *cands])
        sd = np.sqrt(np.diag(cov))
        corr = cov[0, 1:] / (sd[0] * sd[1:])
        same = np.array([universe.table.at[c, "listing"] == universe.table.at[t, "listing"]
                         for c in cands])
        k = int(np.argmax(corr + 0.005 * same))
        out[t] = Replacement(t, cands[k], float(corr[k]),
                             harvest_on + timedelta(days=rules.window_after + 1))
    return out
