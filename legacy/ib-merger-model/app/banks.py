"""Static reference data for the three simulated Swiss banks.

FICTIONAL DATA. Aareland Regionalbank, Novafin Kreditbank and Banca Alpina do
not exist. Every figure is invented for an educational M&A case study set in
the Swiss market. Nothing here is financial advice.

Currency is CHF millions throughout. Anchor year FY2025.

Why the numbers differ from a North American equivalent
-------------------------------------------------------
Swiss law reshapes the economics, not just the labels:

*  Consumer credit rates are capped. The Konsumkreditgesetz (KKG) and its
   ordinance (VKKG) put a ceiling on consumer lending rates - around 12% for
   cash credit and a little higher for card overdrafts. There is no 21% card
   APR in this market, so the interest spread that makes card lending
   attractive is roughly a third narrower than in Canada or the US.
*  Losses are correspondingly lower. The KKG requires a formal affordability
   assessment (Kreditfahigkeitsprufung) before any limit is granted or raised,
   and every consumer credit and card limit must be reported to the IKO
   register. Combined with strong debt enforcement (Betreibung), Swiss card
   loss rates run well below North American ones.
*  Balance sheets are mortgage-heavy. Swiss retail banks are, in substance,
   mortgage lenders with a bank attached. Mortgage LGD is very low: full
   recourse, conservative loan-to-value limits, and mandatory amortisation.
*  Capital ratios are higher. The Swiss finish under the Eigenmittelverordnung
   (ERV) plus FINMA buffer requirements put CET1 well above Basel minimums.
*  Profitability is lower. Narrow spreads and high capital mean Swiss regional
   banks earn returns on equity in the high single digits, not the low teens.

See swiss_notes.py for the full regulatory commentary surfaced in the app.
"""

from dataclasses import dataclass, asdict

import pandas as pd

BANKS = [
    "Aareland Regionalbank (A)",
    "Novafin Kreditbank (B)",
    "Banca Alpina (C)",
]
SHORT = {
    "Aareland Regionalbank (A)": "A",
    "Novafin Kreditbank (B)": "B",
    "Banca Alpina (C)": "C",
}

# The four economic regions the case is cut by.
REGIONS = ["Romandie", "Mittelland", "Alpen", "Tessin"]
CLIENT_TYPES = ["Privatkunden (individuals)", "Firmenkunden (companies)"]

INDIVIDUALS = "Privatkunden (individuals)"
COMPANIES = "Firmenkunden (companies)"

CURRENCY = "CHF"

# Swiss corporate tax. Cantonal, so the domicile of the combined entity is a
# genuine M&A decision: Zurich sits near 19.7%, Zug closer to 11.9%.
TAX_RATE = 0.197
TAX_CANTON = "Zurich"

# Federal issuance stamp duty (Emissionsabgabe) on new equity, 1% above a
# CHF 1m exemption. It survived the 2022 referendum, so an equity raise to
# fund an acquisition carries this cost.
STAMP_DUTY_RATE = 0.01
STAMP_DUTY_EXEMPTION = 1.0


# --------------------------------------------------------------------------
# Bank-level figures (FY2025 anchor, CHF mm)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BankFacts:
    name: str
    total_assets: float
    equity: float
    cet1: float
    rwa: float              # total regulatory RWA under the ERV
    net_income: float
    deposits: float
    shares_mm: float
    price: float
    card_revolve_rate: float
    card_apr: float         # capped by the KKG/VKKG
    funding_cost: float
    allowance: float        # Wertberichtigungen fur Ausfallrisiken
    pcl: float              # annual charge for default risks
    general_reserve: float  # Reserven fur allgemeine Bankrisiken
    finma_category: int     # FINMA supervisory category (1 largest, 5 smallest)


BANK_FACTS = {
    "Aareland Regionalbank (A)": BankFacts(
        name="Aareland Regionalbank (A)",
        total_assets=41_000, equity=3_300, cet1=3_050, rwa=17_900,
        net_income=285, deposits=30_500, shares_mm=24.0, price=185.00,
        card_revolve_rate=0.28, card_apr=0.1195, funding_cost=0.0075,
        allowance=165, pcl=38, general_reserve=420, finma_category=3,
    ),
    "Novafin Kreditbank (B)": BankFacts(
        name="Novafin Kreditbank (B)",
        total_assets=7_200, equity=720, cet1=640, rwa=5_400,
        net_income=145, deposits=3_900, shares_mm=0.0, price=0.0,
        card_revolve_rate=0.62, card_apr=0.1290, funding_cost=0.0185,
        allowance=175, pcl=96, general_reserve=85, finma_category=4,
    ),
    "Banca Alpina (C)": BankFacts(
        name="Banca Alpina (C)",
        total_assets=8_400, equity=800, cet1=760, rwa=3_700,
        net_income=46, deposits=6_900, shares_mm=0.0, price=0.0,
        card_revolve_rate=0.24, card_apr=0.1090, funding_cost=0.0060,
        allowance=52, pcl=9, general_reserve=155, finma_category=4,
    ),
}


# --------------------------------------------------------------------------
# Product-level portfolio
# --------------------------------------------------------------------------

@dataclass
class Product:
    bank: str
    client_type: str
    product: str
    drawn: float
    undrawn: float
    pd: float
    lgd: float
    risk_weight: float
    ccf: float
    revolving: bool
    # ---- Swiss GAAP (FINMA Circular 2020/1) -----------------------------
    impaired: float       # share of drawn that is gefahrdet -> individual
                          # value adjustment (Einzelwertberichtigung)
    inherent: float       # rate applied to the performing book for inherent
                          # default risks (inharente Ausfallrisiken)
    # ---- IFRS 9 shadow, for the comparison view -------------------------
    stage2: float         # share that would sit in IFRS 9 stage 2
    mortgage: bool        # attracts the sectoral countercyclical buffer


def _card_risk_weight(revolve_rate: float) -> float:
    """Blend the transactor and revolver buckets by revolve rate."""
    return revolve_rate * 0.75 + (1.0 - revolve_rate) * 0.45


_A_CARD_RW = _card_risk_weight(BANK_FACTS["Aareland Regionalbank (A)"].card_revolve_rate)
_B_CARD_RW = _card_risk_weight(BANK_FACTS["Novafin Kreditbank (B)"].card_revolve_rate)
_C_CARD_RW = _card_risk_weight(BANK_FACTS["Banca Alpina (C)"].card_revolve_rate)

# Swiss mortgage risk weights run above the 35% Basel standard figure because
# of the Swiss finish and the loan-to-value add-ons in the ERV.
_MORTGAGE_RW = 0.40


PRODUCTS: list[Product] = [
    # ---- A: Aareland Regionalbank - mortgage-heavy Mittelland retail bank
    Product("Aareland Regionalbank (A)", INDIVIDUALS, "Credit cards",
            640, 2_050, 0.0120, 0.70, _A_CARD_RW, 0.10, True,
            0.014, 0.0040, 0.048, False),
    Product("Aareland Regionalbank (A)", INDIVIDUALS, "Mortgages",
            24_500, 0, 0.0020, 0.12, _MORTGAGE_RW, 0.00, False,
            0.006, 0.0008, 0.021, True),
    Product("Aareland Regionalbank (A)", INDIVIDUALS, "Other consumer",
            1_450, 0, 0.0105, 0.62, 0.75, 0.00, False,
            0.012, 0.0032, 0.038, False),
    Product("Aareland Regionalbank (A)", COMPANIES, "Commercial & SME",
            6_800, 950, 0.0120, 0.35, 0.85, 0.40, True,
            0.017, 0.0045, 0.052, False),

    # ---- B: Novafin Kreditbank - consumer credit and card specialist
    Product("Novafin Kreditbank (B)", INDIVIDUALS, "Credit cards",
            3_850, 5_900, 0.0280, 0.74, _B_CARD_RW, 0.10, True,
            0.038, 0.0105, 0.098, False),
    Product("Novafin Kreditbank (B)", INDIVIDUALS, "Installment loans",
            2_100, 0, 0.0225, 0.68, 0.75, 0.00, False,
            0.030, 0.0085, 0.082, False),

    # ---- C: Banca Alpina - conservative, concentrated south of the Alps
    Product("Banca Alpina (C)", INDIVIDUALS, "Credit cards",
            165, 520, 0.0090, 0.66, _C_CARD_RW, 0.10, True,
            0.010, 0.0028, 0.034, False),
    Product("Banca Alpina (C)", INDIVIDUALS, "Mortgages",
            5_200, 0, 0.0015, 0.11, _MORTGAGE_RW, 0.00, False,
            0.005, 0.0006, 0.017, True),
    Product("Banca Alpina (C)", INDIVIDUALS, "Other consumer",
            340, 0, 0.0085, 0.60, 0.75, 0.00, False,
            0.010, 0.0026, 0.030, False),
    Product("Banca Alpina (C)", COMPANIES, "Commercial & SME",
            950, 140, 0.0105, 0.34, 0.85, 0.40, True,
            0.015, 0.0040, 0.046, False),
]


# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------

# Aareland is a Mittelland bank with a real Romandie presence. Novafin lends
# nationally through brokers and retail partners. Banca Alpina is a Lugano
# house with nearly two thirds of its book in Ticino - safe on average
# metrics, but concentrated, which is what the regional view is built to show.
REGION_MIX = {
    "Aareland Regionalbank (A)": {
        "Romandie": 0.30, "Mittelland": 0.48, "Alpen": 0.15, "Tessin": 0.07,
    },
    "Novafin Kreditbank (B)": {
        "Romandie": 0.31, "Mittelland": 0.45, "Alpen": 0.14, "Tessin": 0.10,
    },
    "Banca Alpina (C)": {
        "Romandie": 0.04, "Mittelland": 0.08, "Alpen": 0.24, "Tessin": 0.64,
    },
}

# Intrinsic regional credit quality, as a multiplier on base PD. Ticino and
# the Romandie carry structurally higher unemployment than the Mittelland.
REGION_PD_MULT = {
    "Romandie": 1.08,
    "Mittelland": 0.92,
    "Alpen": 1.05,
    "Tessin": 1.20,
}

# How hard each region reacts to a given macro move.
#
#   Mittelland - the economic core; most rate- and property-sensitive, since
#                Zurich carries the highest valuations.
#   Romandie   - Geneva finance and trading plus the watch industry in the
#                Jura arc, so export- and franc-sensitive.
#   Alpen      - tourism and construction; a strong franc empties the hotels,
#                and seasonal employment amplifies any labour-market move.
#   Tessin     - cross-border workers and dependence on the Italian economy;
#                the most employment-sensitive region and highly franc-exposed.
REGION_MACRO_AMP = {
    "Romandie":   {"unemployment": 1.15, "gdp": 1.05, "rate": 1.00,
                   "property": 1.20, "chf": 1.25},
    "Mittelland": {"unemployment": 1.00, "gdp": 1.00, "rate": 1.15,
                   "property": 1.35, "chf": 0.85},
    "Alpen":      {"unemployment": 1.25, "gdp": 1.15, "rate": 0.85,
                   "property": 0.75, "chf": 1.60},
    "Tessin":     {"unemployment": 1.35, "gdp": 1.20, "rate": 0.90,
                   "property": 0.85, "chf": 1.45},
}


def base_portfolio() -> pd.DataFrame:
    """Expand products across regions into the line-item exposure table."""
    rows = []
    for p in PRODUCTS:
        for region, weight in REGION_MIX[p.bank].items():
            row = asdict(p)
            row["region"] = region
            row["drawn"] = p.drawn * weight
            row["undrawn"] = p.undrawn * weight
            row["pd"] = p.pd * REGION_PD_MULT[region]
            rows.append(row)

    df = pd.DataFrame(rows)
    return df[[
        "bank", "client_type", "product", "region",
        "drawn", "undrawn", "pd", "lgd", "risk_weight", "ccf",
        "revolving", "impaired", "inherent", "stage2", "mortgage",
    ]]


def product_table() -> pd.DataFrame:
    """Product-level view, the grain the data editor exposes to the user."""
    df = pd.DataFrame([asdict(p) for p in PRODUCTS])
    df = df[[
        "bank", "client_type", "product",
        "drawn", "undrawn", "pd", "lgd", "risk_weight", "ccf",
        "revolving", "impaired", "inherent", "stage2", "mortgage",
    ]]
    for col in ("drawn", "undrawn", "pd", "lgd", "risk_weight", "ccf",
                "impaired", "inherent", "stage2"):
        df[col] = df[col].astype(float)
    return df


DISCLAIMER = (
    "All entities, financial figures and events in this application are entirely "
    "fictional, created for illustrative and educational simulation purposes. They "
    "do not represent any real institution, and nothing here is financial, "
    "investment, legal, tax or M&A advice. The regulatory commentary is a "
    "simplified summary for teaching purposes and is not a statement of Swiss law."
)
