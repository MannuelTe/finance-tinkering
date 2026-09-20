"""Macro-to-credit transmission and capital engine, Swiss version.

The chain, per exposure line (bank x client type x product x region):

    macro shock -> PD multiplier        (regional amplifiers applied)
                -> LGD adjustment       (collateral value; mortgages dominate)
                -> exposure migration   (revolvers draw down, KKG-constrained)
                -> Swiss GAAP value adjustments
                -> value adjustments, RWA, CET1

Three Swiss features shape this differently from an IFRS 9 model:

1.  **No three-stage staging.** Swiss GAAP books an individual value
    adjustment when an exposure actually deteriorates, plus a provision for
    inherent default risks across the performing book. There is no jump to
    lifetime expected loss on a forecast. The engine computes the Swiss figure
    as the headline and an IFRS 9 shadow alongside it, so the divergence is
    visible rather than assumed away.

2.  **The franc is a risk factor.** A strong Swiss franc hurts exporters,
    tourism and the cross-border economy, so it is modelled explicitly rather
    than folded into GDP. It is what makes the Alpen and Tessin regions behave
    differently from the Mittelland.

3.  **Mortgages carry a sectoral capital buffer** on top of ordinary RWA, so
    mortgage-heavy books cost more capital than their risk weights imply.

All coefficients are invented for this simulation and are not calibrated to
any real portfolio.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import banks as bk

TAX_RATE = bk.TAX_RATE

# --- capital requirements (Swiss finish under the ERV) --------------------
CET1_MANAGEMENT_TARGET = 0.120   # the acquirer's internal target
CET1_REGULATORY_MIN = 0.080      # minimum incl. buffers, FINMA category 3
SECTORAL_CCYB = 0.025            # sectoral buffer on Swiss residential mortgages


# --------------------------------------------------------------------------
# Transmission coefficients
# --------------------------------------------------------------------------
# Units: per +1pp unemployment, per -1pp GDP growth, per +100bp policy rate,
# per -10% property prices, per +10% franc appreciation.
#
# Swiss unemployment sits near 2.5%, so a one-point move is proportionally
# larger than the same move in a market with 6% unemployment. The employment
# betas are scaled up accordingly.

PD_BETAS = {
    "Credit cards":     {"unemployment": 0.30, "gdp": 0.080, "rate": 0.050,
                         "property": 0.015, "chf": 0.030},
    "Mortgages":        {"unemployment": 0.22, "gdp": 0.060, "rate": 0.110,
                         "property": 0.055, "chf": 0.020},
    "Other consumer":   {"unemployment": 0.26, "gdp": 0.070, "rate": 0.050,
                         "property": 0.015, "chf": 0.030},
    "Installment loans": {"unemployment": 0.26, "gdp": 0.070, "rate": 0.050,
                          "property": 0.015, "chf": 0.030},
    "Commercial & SME": {"unemployment": 0.12, "gdp": 0.210, "rate": 0.080,
                         "property": 0.025, "chf": 0.140},
}

# Loss given default follows collateral value. Swiss mortgage lending is full
# recourse with mandatory amortisation, so even here the response is modest.
LGD_BETAS = {
    "Credit cards":     {"property": 0.010, "gdp": 0.010},
    "Mortgages":        {"property": 0.150, "gdp": 0.025},
    "Other consumer":   {"property": 0.015, "gdp": 0.020},
    "Installment loans": {"property": 0.015, "gdp": 0.020},
    "Commercial & SME": {"property": 0.070, "gdp": 0.060},
}

# Lifetime multiple used only in the IFRS 9 shadow calculation.
LIFETIME_MULT = {
    "Credit cards": 3.2,
    "Mortgages": 4.5,
    "Other consumer": 2.8,
    "Installment loans": 2.6,
    "Commercial & SME": 2.8,
}

# The KKG affordability test already assumes an overdraft facility is drawn to
# its full limit before the limit is granted, so Swiss headroom is smaller
# relative to borrower capacity and the drawdown response is milder than in an
# unregulated market.
HEADROOM_CONSUMPTION = 0.06
CCF_MIGRATION = 0.14
CCF_CAP = 0.60

# Swiss GAAP: impairment is recognised as it is incurred, so the impaired
# share lags the cycle. The inherent-risk provision moves more slowly still.
IMPAIRED_SENSITIVITY = 0.35
INHERENT_SENSITIVITY = 0.25

# IFRS 9 shadow: stage 2 migration is forward-looking and jumps.
IFRS9_STAGE2_SENSITIVITY = 0.55

REVOLVER_RW_DRIFT = 0.35
REVOLVER_RW_CAP = 0.75

STRESS_W_UNEMPLOYMENT = 0.22
STRESS_W_GDP = 0.15
STRESS_W_RATE = 0.08
STRESS_W_PROPERTY = 0.05
STRESS_W_CHF = 0.06


# --------------------------------------------------------------------------
# Scenario definition
# --------------------------------------------------------------------------

@dataclass
class Macro:
    """A macro shock, expressed as deviations from the FY2025 base."""
    unemployment: float = 0.0   # percentage points, +ve = worse
    gdp: float = 0.0            # percentage points of growth, -ve = worse
    rate: float = 0.0           # basis points, SNB policy rate
    property: float = 0.0       # percent change in property prices
    chf: float = 0.0            # percent appreciation of the franc, +ve = worse

    def is_base(self) -> bool:
        return not any((self.unemployment, self.gdp, self.rate,
                        self.property, self.chf))


@dataclass
class Levers:
    """Management actions applied on top of the macro scenario."""
    limit_increase: float = 0.0
    book_growth: float = 0.0
    underwriting: float = 0.0


@dataclass
class Scenario:
    macro: Macro = field(default_factory=Macro)
    regional: dict[str, Macro] = field(default_factory=dict)
    levers: dict[str, Levers] = field(default_factory=dict)

    def for_region(self, region: str) -> Macro:
        return self.regional.get(region, self.macro)


PRESETS: dict[str, Macro] = {
    "Base (FY2025 actual)":   Macro(0.0, 0.0, 0, 0.0, 0.0),
    "Mild slowdown":          Macro(0.8, -1.0, 0, -5.0, 3.0),
    "Recession":              Macro(2.0, -2.5, -75, -12.0, 8.0),
    "Severe recession":       Macro(3.2, -4.5, -125, -22.0, 15.0),
    "SNB rate shock":         Macro(0.5, -0.5, 250, -12.0, 6.0),
    "Property correction":    Macro(0.8, -1.0, 50, -28.0, 2.0),
    "Franc shock":            Macro(1.2, -2.0, -100, -3.0, 20.0),
}

PRESET_NOTES = {
    "Franc shock": (
        "A sharp franc appreciation of the kind seen when the SNB abandoned the "
        "euro floor in January 2015. Exporters, tourism and the cross-border "
        "economy take the damage, so the Alpen and Tessin regions bear far more "
        "of it than the Mittelland."
    ),
    "Property correction": (
        "A property-led downturn. Swiss mortgage lending is full recourse with "
        "mandatory amortisation, so this shows up in capital through the sectoral "
        "buffer and collateral values rather than as a wave of defaults."
    ),
    "SNB rate shock": (
        "An abrupt tightening. Swiss mortgages are heavily fixed-rate, so the "
        "credit effect builds slowly, but property valuations react at once."
    ),
}


# --------------------------------------------------------------------------
# Core computation
# --------------------------------------------------------------------------

def _stress_index(m: Macro, amp: dict[str, float]) -> float:
    """A scalar summary of how bad conditions are, driving the behavioural
    responses (drawdown, impairment migration) that are not PD itself."""
    return max(0.0, (
        STRESS_W_UNEMPLOYMENT * amp["unemployment"] * m.unemployment
        + STRESS_W_GDP * amp["gdp"] * max(0.0, -m.gdp)
        + STRESS_W_RATE * amp["rate"] * (m.rate / 100.0)
        + STRESS_W_PROPERTY * amp["property"] * max(0.0, -m.property / 10.0)
        + STRESS_W_CHF * amp["chf"] * max(0.0, m.chf / 10.0)
    ))


def compute(
    portfolio: pd.DataFrame,
    scenario: Scenario,
    calibration: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Apply a scenario to the exposure table.

    `calibration` scales modelled value adjustments so the base case
    reproduces each bank's carried allowance - see `va_calibration`.
    """
    df = portfolio.copy()

    # --- management levers, applied before the macro shock ----------------
    lev_growth = df["bank"].map(
        lambda b: 1.0 + scenario.levers.get(b, Levers()).book_growth / 100.0)
    lev_limit = df["bank"].map(
        lambda b: 1.0 + scenario.levers.get(b, Levers()).limit_increase / 100.0)
    lev_uw = df["bank"].map(
        lambda b: 1.0 + scenario.levers.get(b, Levers()).underwriting / 100.0)

    df["drawn"] = df["drawn"] * lev_growth
    df["undrawn"] = np.where(df["revolving"], df["undrawn"] * lev_limit, df["undrawn"])
    df["pd"] = (df["pd"] * lev_uw).clip(0.0001, 1.0)

    # --- per-row macro inputs --------------------------------------------
    macro_rows = df["region"].map(scenario.for_region)
    amp_rows = df["region"].map(bk.REGION_MACRO_AMP)

    du = macro_rows.map(lambda m: m.unemployment).astype(float)
    dg = macro_rows.map(lambda m: m.gdp).astype(float)
    dr = macro_rows.map(lambda m: m.rate).astype(float)
    dp = macro_rows.map(lambda m: m.property).astype(float)
    dc = macro_rows.map(lambda m: m.chf).astype(float)

    amp_u = amp_rows.map(lambda a: a["unemployment"]).astype(float)
    amp_g = amp_rows.map(lambda a: a["gdp"]).astype(float)
    amp_r = amp_rows.map(lambda a: a["rate"]).astype(float)
    amp_p = amp_rows.map(lambda a: a["property"]).astype(float)
    amp_c = amp_rows.map(lambda a: a["chf"]).astype(float)

    pb = df["product"].map(PD_BETAS)
    b_u = pb.map(lambda d: d["unemployment"]).astype(float)
    b_g = pb.map(lambda d: d["gdp"]).astype(float)
    b_r = pb.map(lambda d: d["rate"]).astype(float)
    b_p = pb.map(lambda d: d["property"]).astype(float)
    b_c = pb.map(lambda d: d["chf"]).astype(float)

    lb = df["product"].map(LGD_BETAS)
    l_p = lb.map(lambda d: d["property"]).astype(float)
    l_g = lb.map(lambda d: d["gdp"]).astype(float)

    stress = pd.Series(
        [_stress_index(m, a) for m, a in zip(macro_rows, amp_rows)],
        index=df.index, dtype=float,
    )
    df["stress_index"] = stress

    # --- PD ---------------------------------------------------------------
    ln_pd = (
        b_u * amp_u * du
        + b_g * amp_g * (-dg)
        + b_r * amp_r * (dr / 100.0)
        + b_p * amp_p * (-dp / 10.0)
        + b_c * amp_c * (dc / 10.0)
    )
    df["pd_stressed"] = (df["pd"] * np.exp(ln_pd)).clip(0.0, 0.99)

    # --- LGD --------------------------------------------------------------
    ln_lgd = l_p * amp_p * (-dp / 10.0) + l_g * amp_g * (-dg)
    df["lgd_stressed"] = (df["lgd"] * np.exp(ln_lgd)).clip(0.0, 0.95)

    # --- exposure migration ----------------------------------------------
    consume = np.where(
        df["revolving"],
        np.minimum(0.45, HEADROOM_CONSUMPTION * stress),
        0.0,
    )
    extra_draw = df["undrawn"] * consume
    df["drawn_stressed"] = df["drawn"] + extra_draw
    df["undrawn_stressed"] = df["undrawn"] - extra_draw

    df["ccf_effective"] = np.where(
        df["revolving"],
        np.minimum(CCF_CAP, df["ccf"] + CCF_MIGRATION * stress),
        df["ccf"],
    )

    df["ead_base"] = df["drawn"] + df["undrawn"] * df["ccf"]
    df["ead_stressed"] = df["drawn_stressed"] + df["undrawn_stressed"] * df["ccf_effective"]
    df["ead_regulatory"] = df["drawn_stressed"] + df["undrawn_stressed"] * df["ccf"]

    # --- Swiss GAAP value adjustments -------------------------------------
    # Individual adjustments on impaired exposures, plus a provision for
    # inherent default risks across what is still performing. Impairment is
    # recognised as incurred, so it migrates slowly.
    df["impaired_stressed"] = np.minimum(
        0.45, df["impaired"] * (1 + IMPAIRED_SENSITIVITY * stress))
    df["inherent_stressed"] = np.minimum(
        0.12, df["inherent"] * (1 + INHERENT_SENSITIVITY * stress))

    df["va_base"] = (
        df["drawn"] * df["impaired"] * df["lgd"]
        + df["drawn"] * (1 - df["impaired"]) * df["inherent"]
        + df["undrawn"] * df["ccf"] * df["inherent"]
    )
    df["va_stressed"] = (
        df["drawn_stressed"] * df["impaired_stressed"] * df["lgd_stressed"]
        + df["drawn_stressed"] * (1 - df["impaired_stressed"]) * df["inherent_stressed"]
        + df["undrawn_stressed"] * df["ccf_effective"] * df["inherent_stressed"]
    )

    # --- IFRS 9 shadow, for the comparison view ---------------------------
    # What the same book would have required under three-stage staging. The
    # stage 1 -> 2 step multiplies the reserve by the lifetime factor without
    # a missed payment, which is the divergence the explainer describes.
    life = df["product"].map(LIFETIME_MULT).astype(float)
    s3 = df["impaired"]
    s3_str = df["impaired_stressed"]
    s2 = df["stage2"]
    s2_str = np.minimum(0.65, df["stage2"] * (1 + IFRS9_STAGE2_SENSITIVITY * stress))
    s1 = (1 - s2 - s3).clip(0.0, 1.0)
    s1_str = (1 - s2_str - s3_str).clip(0.0, 1.0)

    df["ifrs9_base"] = (
        df["drawn"] * df["lgd"] * (s1 * df["pd"] + s2 * df["pd"] * life + s3)
        + df["undrawn"] * df["ccf"] * df["lgd"] * df["pd"]
    )
    df["ifrs9_stressed"] = (
        df["drawn_stressed"] * df["lgd_stressed"]
        * (s1_str * df["pd_stressed"] + s2_str * df["pd_stressed"] * life + s3_str)
        + df["undrawn_stressed"] * df["ccf_effective"]
        * df["lgd_stressed"] * df["pd_stressed"]
    )

    if calibration:
        factor = df["bank"].map(calibration).fillna(1.0).astype(float)
        for col in ("va_base", "va_stressed", "ifrs9_base", "ifrs9_stressed"):
            df[col] = df[col] * factor

    df["va_delta"] = df["va_stressed"] - df["va_base"]
    df["ifrs9_delta"] = df["ifrs9_stressed"] - df["ifrs9_base"]
    df["gaap_gap"] = df["ifrs9_stressed"] - df["va_stressed"]

    # Simple 12-month expected loss, for the risk-profile view.
    df["el_base"] = df["ead_base"] * df["lgd"] * df["pd"]
    df["el_stressed"] = df["ead_stressed"] * df["lgd_stressed"] * df["pd_stressed"]
    df["el_rate"] = np.where(
        df["ead_stressed"] > 0, df["el_stressed"] / df["ead_stressed"], 0.0)

    # --- risk-weighted assets --------------------------------------------
    headroom_to_cap = np.maximum(0.0, REVOLVER_RW_CAP - df["risk_weight"])
    rw_stressed = np.where(
        df["revolving"],
        df["risk_weight"] + headroom_to_cap * np.minimum(1.0, REVOLVER_RW_DRIFT * stress),
        df["risk_weight"],
    )
    df["risk_weight_stressed"] = rw_stressed
    df["rwa_base"] = df["ead_base"] * df["risk_weight"]
    df["rwa_stressed"] = df["ead_regulatory"] * rw_stressed

    # Mortgage RWA is tracked separately because it carries the sectoral
    # countercyclical buffer on top of the ordinary requirement.
    df["mortgage_rwa_base"] = np.where(df["mortgage"], df["rwa_base"], 0.0)
    df["mortgage_rwa_stressed"] = np.where(df["mortgage"], df["rwa_stressed"], 0.0)

    return df


# --------------------------------------------------------------------------
# Calibration and aggregation
# --------------------------------------------------------------------------

def va_calibration(base_rows: pd.DataFrame) -> dict[str, float]:
    """Scale factor per bank so base modelled value adjustments equal the
    carried allowance.

    A factor well below 1.0 says the bank carries materially less reserve than
    this model implies its book needs.
    """
    modelled = base_rows.groupby("bank", observed=True)["va_base"].sum()
    out = {}
    for b in bk.BANKS:
        m = float(modelled.get(b, 0.0))
        out[b] = (bk.BANK_FACTS[b].allowance / m) if m > 0 else 1.0
    return out


def other_rwa_plug(base_rows: pd.DataFrame) -> dict[str, float]:
    """Residual RWA (securities, operational risk, other assets) that makes
    the base case reconcile exactly to each bank's reported total RWA."""
    credit = base_rows.groupby("bank", observed=True)["rwa_base"].sum()
    return {
        b: float(bk.BANK_FACTS[b].rwa - credit.get(b, 0.0))
        for b in bk.BANKS
    }


def required_cet1(total_rwa: float, mortgage_rwa: float) -> float:
    """Management target plus the sectoral buffer on mortgage positions."""
    return CET1_MANAGEMENT_TARGET * total_rwa + SECTORAL_CCYB * mortgage_rwa


def bank_summary(df: pd.DataFrame, plug: dict[str, float]) -> pd.DataFrame:
    """Roll the exposure table up to one row per bank."""
    g = df.groupby("bank", observed=True).agg(
        drawn=("drawn", "sum"),
        undrawn=("undrawn", "sum"),
        drawn_stressed=("drawn_stressed", "sum"),
        undrawn_stressed=("undrawn_stressed", "sum"),
        ead_base=("ead_base", "sum"),
        ead_stressed=("ead_stressed", "sum"),
        el_base=("el_base", "sum"),
        el_stressed=("el_stressed", "sum"),
        va_base=("va_base", "sum"),
        va_stressed=("va_stressed", "sum"),
        ifrs9_base=("ifrs9_base", "sum"),
        ifrs9_stressed=("ifrs9_stressed", "sum"),
        rwa_credit_base=("rwa_base", "sum"),
        rwa_credit_stressed=("rwa_stressed", "sum"),
        mortgage_rwa=("mortgage_rwa_stressed", "sum"),
        mortgage_rwa_base=("mortgage_rwa_base", "sum"),
    ).reset_index()

    g["other_rwa"] = g["bank"].map(plug)
    g["rwa_base_total"] = g["rwa_credit_base"] + g["other_rwa"]
    g["rwa_stressed_total"] = g["rwa_credit_stressed"] + g["other_rwa"]

    g["cet1_base"] = g["bank"].map(lambda b: bk.BANK_FACTS[b].cet1)
    g["va_delta"] = g["va_stressed"] - g["va_base"]
    g["ifrs9_delta"] = g["ifrs9_stressed"] - g["ifrs9_base"]
    g["gaap_gap"] = g["ifrs9_stressed"] - g["va_stressed"]

    g["cet1_stressed"] = g["cet1_base"] - g["va_delta"] * (1 - TAX_RATE)

    g["cet1_ratio_base"] = g["cet1_base"] / g["rwa_base_total"]
    g["cet1_ratio_stressed"] = g["cet1_stressed"] / g["rwa_stressed_total"]

    # Requirement including the sectoral mortgage buffer.
    g["required_cet1"] = [
        required_cet1(r, m) for r, m in zip(g["rwa_stressed_total"], g["mortgage_rwa"])
    ]
    g["cet1_surplus"] = g["cet1_stressed"] - g["required_cet1"]
    g["sectoral_buffer"] = SECTORAL_CCYB * g["mortgage_rwa"]

    g["el_rate_base"] = g["el_base"] / g["ead_base"].replace(0, np.nan)
    g["el_rate_stressed"] = g["el_stressed"] / g["ead_stressed"].replace(0, np.nan)

    # Reserves for general banking risks smooth the income statement. They sit
    # inside CET1 either way, so releasing them changes reported earnings, not
    # capital - which is exactly the point worth showing.
    g["general_reserve"] = g["bank"].map(lambda b: bk.BANK_FACTS[b].general_reserve)
    g["net_income_base"] = g["bank"].map(lambda b: bk.BANK_FACTS[b].net_income)
    charge = g["va_delta"] * (1 - TAX_RATE)
    g["net_income_before_release"] = g["net_income_base"] - charge
    g["reserve_release"] = np.minimum(g["general_reserve"], charge.clip(lower=0))
    g["net_income_stressed"] = g["net_income_before_release"] + g["reserve_release"]

    return g


def breakdown(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Aggregate the exposure table along any set of dimensions."""
    g = df.groupby(by, observed=True).agg(
        ead_base=("ead_base", "sum"),
        ead_stressed=("ead_stressed", "sum"),
        drawn=("drawn", "sum"),
        undrawn=("undrawn", "sum"),
        el_base=("el_base", "sum"),
        el_stressed=("el_stressed", "sum"),
        va_base=("va_base", "sum"),
        va_stressed=("va_stressed", "sum"),
        ifrs9_stressed=("ifrs9_stressed", "sum"),
        rwa_stressed=("rwa_stressed", "sum"),
    ).reset_index()

    g["el_rate_base"] = g["el_base"] / g["ead_base"].replace(0, np.nan)
    g["el_rate_stressed"] = g["el_stressed"] / g["ead_stressed"].replace(0, np.nan)
    g["el_delta"] = g["el_stressed"] - g["el_base"]
    g["va_delta"] = g["va_stressed"] - g["va_base"]
    g["gaap_gap"] = g["ifrs9_stressed"] - g["va_stressed"]
    return g


def concentration_hhi(df: pd.DataFrame, bank: str, dim: str = "region") -> float:
    """Herfindahl-Hirschman index of exposure concentration, 0-1.

    With four regions, 0.25 is perfectly even and 1.0 is everything in one
    place.
    """
    sub = df[df["bank"] == bank]
    total = sub["ead_stressed"].sum()
    if total <= 0:
        return 0.0
    shares = sub.groupby(dim, observed=True)["ead_stressed"].sum() / total
    return float((shares ** 2).sum())
